#!/usr/bin/env python3
"""Generate and locally validate one small Stage-6 SceneSpec per provider.

This is a spend-bounded integration smoke test.  It never starts CARLA and it
only permits one request per selected provider.  The script records the prompt,
raw API response, extracted JSON, local validation result, reported usage, and
timing in an ignored run directory.  API keys are read from ``.env`` or the
process environment and are never written to disk or stdout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from stage6_api_access_check import environment_value, load_dotenv, utc_now
from stage6_scene_spec import (
    SceneSpecError,
    load_route_geometry,
    load_stage6_config,
    parse_scene_spec_json,
    resolve_scene_spec,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
DEFAULT_OPENAI_MODEL = "gpt-6-astra"
DEFAULT_DASHSCOPE_MODEL = "qwen3-8b"

SYSTEM_PROMPT = (
    "You are a constrained CARLA scene planner. Return only one JSON object and no Markdown. "
    "The JSON must be a passive Stage-6 SceneSpec; never include code, direct world coordinates, "
    "or extra fields."
)
USER_PROMPT = """Create a SceneSpec for this natural-language request: on the fixed straight route in Town01_Opt, use wet_cloudy_day and park exactly one vehicle.audi.a2 10 metres to the left of the route at 40 metres of route progress. Use a valid integer seed.

Return exactly this JSON shape:
{
  "version": "1.0",
  "map_name": "Town01_Opt",
  "route_id": "route_01_straight",
  "weather_id": "wet_cloudy_day",
  "seed": 1,
  "edits": [
    {
      "operation": "spawn_parked_vehicle",
      "blueprint_id": "vehicle.audi.a2",
      "anchor": {"route_progress_m": 40.0, "side": "left"},
      "longitudinal_offset_m": 0.0,
      "lateral_offset_m": 10.0
    }
  ]
}"""


class ProviderResponseError(RuntimeError):
    """A provider response lacked a completed JSON text output."""


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def post_json(url: str, api_key: str, body: dict[str, object], timeout_s: float) -> tuple[int, dict[str, Any], float]:
    """POST JSON without exposing the Authorization header in failures."""
    started = time.monotonic()
    encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=encoded,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            status = int(response.status)
            raw = response.read()
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        raw = exc.read()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ProviderResponseError("provider response is not a JSON object")
    return status, payload, time.monotonic() - started


def extract_openai_response_text(payload: dict[str, Any]) -> str:
    if payload.get("status") != "completed":
        details = payload.get("incomplete_details")
        raise ProviderResponseError(f"OpenAI response status is {payload.get('status')!r}; details={details!r}")
    for item in payload.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") == "refusal":
                raise ProviderResponseError("OpenAI model returned a refusal")
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                return content["text"]
    raise ProviderResponseError("OpenAI response had no output_text")


def extract_dashscope_response_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ProviderResponseError("DashScope response had no choices")
    choice = choices[0]
    if choice.get("finish_reason") not in {"stop", None}:
        raise ProviderResponseError(f"DashScope finish_reason is {choice.get('finish_reason')!r}")
    message = choice.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise ProviderResponseError("DashScope response had no message content")
    return message["content"]


def local_validation(response_text: str) -> dict[str, object]:
    """Apply the pre-CARLA SceneSpec policy only; no simulator connection."""
    try:
        spec = parse_scene_spec_json(response_text)
        config = load_stage6_config(PROJECT_ROOT / "configs" / "stage6_scene_editing.json")
        route = load_route_geometry(PROJECT_ROOT, config, spec.route_id)
        resolved = resolve_scene_spec(spec, config, route)
    except SceneSpecError as exc:
        return {"status": "failed", "error": exc.as_dict()}
    return {
        "status": "passed",
        "scene_spec": spec.as_dict(),
        "resolved_scene": resolved.as_dict(),
    }


def openai_request(model: str, max_output_tokens: int) -> dict[str, object]:
    return {
        "model": model,
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT},
        ],
        "max_output_tokens": max_output_tokens,
        "store": False,
        "text": {"format": {"type": "json_object"}},
    }


def dashscope_request(model: str, max_output_tokens: int) -> dict[str, object]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT},
        ],
        "max_tokens": max_output_tokens,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "enable_thinking": False,
    }


def provider_attempt(
    provider: str,
    url: str,
    api_key: str,
    request_body: dict[str, object],
    timeout_s: float,
    run_dir: Path,
) -> dict[str, object]:
    """Perform one bounded request and preserve result files without secrets."""
    try:
        http_status, raw_response, latency_s = post_json(url, api_key, request_body, timeout_s)
        (run_dir / f"raw_response_{provider}.json").write_text(json.dumps(raw_response, indent=2, sort_keys=True) + "\n")
        if not 200 <= http_status < 300:
            return {
                "status": "http_error",
                "http_status": http_status,
                "api_latency_s": round(latency_s, 3),
                "usage": raw_response.get("usage"),
            }
        response_text = (
            extract_openai_response_text(raw_response)
            if provider == "openai"
            else extract_dashscope_response_text(raw_response)
        )
        (run_dir / f"response_text_{provider}.json").write_text(
            json.dumps({"response_text": response_text}, indent=2, sort_keys=True) + "\n"
        )
        validation = local_validation(response_text)
        (run_dir / f"local_validation_{provider}.json").write_text(
            json.dumps(validation, indent=2, sort_keys=True) + "\n"
        )
        return {
            "status": "passed" if validation["status"] == "passed" else "validation_failed",
            "http_status": http_status,
            "api_latency_s": round(latency_s, 3),
            "response_sha256": sha256_text(response_text),
            "usage": raw_response.get("usage"),
            "local_validation_path": f"local_validation_{provider}.json",
        }
    except (OSError, TimeoutError, ValueError, ProviderResponseError) as exc:
        return {"status": "request_error", "error_type": type(exc).__name__, "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--dotenv", type=Path, default=Path(".env"))
    parser.add_argument("--providers", choices=["openai", "dashscope", "both"], default="both")
    parser.add_argument("--max-output-tokens", type=int, default=192)
    parser.add_argument("--timeout-s", type=float, default=60.0)
    args = parser.parse_args()
    if not 16 <= args.max_output_tokens <= 256:
        raise SystemExit("--max-output-tokens must be within 16..256 for this spend-bounded smoke test")
    if args.timeout_s <= 0.0:
        raise SystemExit("--timeout-s must be positive")
    run_dir = args.run_dir.resolve()
    if not (run_dir / "metadata.json").is_file():
        raise SystemExit("run directory was not created by scripts/create_run.py")

    dotenv_values = load_dotenv(args.dotenv)
    openai_key = environment_value("OPENAI_API_KEY", dotenv_values)
    dashscope_key = environment_value("DASHSCOPE_API_KEY", dotenv_values)
    openai_base = environment_value("OPENAI_BASE_URL", dotenv_values) or DEFAULT_OPENAI_BASE_URL
    dashscope_base = environment_value("DASHSCOPE_BASE_URL", dotenv_values) or DEFAULT_DASHSCOPE_BASE_URL
    openai_model = environment_value("OPENAI_MODEL", dotenv_values) or DEFAULT_OPENAI_MODEL
    dashscope_model = environment_value("QWEN_8B_MODEL", dotenv_values) or DEFAULT_DASHSCOPE_MODEL

    selected = ["openai", "dashscope"] if args.providers == "both" else [args.providers]
    (run_dir / "prompt.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "system_prompt": SYSTEM_PROMPT,
                "user_prompt": USER_PROMPT,
                "max_output_tokens": args.max_output_tokens,
                "carla_started": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    result: dict[str, object] = {
        "schema_version": 1,
        "checked_at_utc": utc_now(),
        "test_kind": "one_constrained_scenespec_generation_per_provider",
        "max_output_tokens": args.max_output_tokens,
        "carla_started": False,
        "providers": {},
    }
    providers = result["providers"]
    assert isinstance(providers, dict)
    for provider in selected:
        if provider == "openai":
            if openai_key is None:
                providers[provider] = {"status": "missing_api_key"}
                continue
            model, base_url, key = openai_model, openai_base, openai_key
            body = openai_request(model, args.max_output_tokens)
            url = f"{base_url.rstrip('/')}/responses"
        else:
            if dashscope_key is None:
                providers[provider] = {"status": "missing_api_key"}
                continue
            model, base_url, key = dashscope_model, dashscope_base, dashscope_key
            body = dashscope_request(model, args.max_output_tokens)
            url = f"{base_url.rstrip('/')}/chat/completions"
        (run_dir / f"request_{provider}.json").write_text(
            json.dumps({"provider": provider, "model": model, "url": url, "body": body}, indent=2, sort_keys=True) + "\n"
        )
        providers[provider] = provider_attempt(provider, url, key, body, args.timeout_s, run_dir)

    statuses = [str(item.get("status")) for item in providers.values() if isinstance(item, dict)]
    result["status"] = "passed" if statuses and all(status == "passed" for status in statuses) else "failed"
    output_path = run_dir / "generation_smoke.json"
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(output_path)
    if result["status"] != "passed":
        raise SystemExit("one or more generation smoke tests did not pass")


if __name__ == "__main__":
    main()
