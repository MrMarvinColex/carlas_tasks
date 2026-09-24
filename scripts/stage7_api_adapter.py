#!/usr/bin/env python3
"""Call the three APIs once for the verified, passive deer SceneSpec.

The adapter never executes model text.  It saves sanitized requests, raw
responses, extracted JSON, strict validation and timings before any CARLA
executor receives a SceneSpec.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from stage6_api_access_check import environment_value, load_dotenv, utc_now
from stage6_api_generation_smoke import (
    ProviderResponseError,
    extract_dashscope_response_text,
    extract_openai_response_text,
    post_json,
)
from stage6_api_adapter import dashscope_request, openai_request
from stage7_scene_spec import (
    SceneSpecError,
    canonical_json_sha256,
    load_stage7_config,
    load_stage7_route,
    parse_scene_spec_json,
    resolve_scene_spec,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL_PATH = Path("configs/stage7_api_protocol.json")
PROMPT_VERSION = "stage7-verified-deer-crossing-v1"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_protocol(path: Path) -> dict[str, Any]:
    protocol = load_object(path)
    required = {"schema_version", "protocol_id", "description", "scene_config", "request_limits", "models", "task"}
    missing = sorted(required - set(protocol))
    if protocol.get("schema_version") != 1 or missing or set(protocol) != required:
        raise ValueError("unsupported or malformed Stage-7 API protocol")
    limits = protocol["request_limits"]
    if not isinstance(limits, dict) or set(limits) != {"repeat_count", "retry_count", "timeout_s", "max_output_tokens", "maximum_total_requests"}:
        raise ValueError("malformed request_limits")
    if int(limits["repeat_count"]) != 1 or int(limits["retry_count"]) != 0:
        raise ValueError("Stage-7 protocol permits exactly one first attempt and no retries")
    if not 16 <= int(limits["max_output_tokens"]) <= 256 or float(limits["timeout_s"]) <= 0.0:
        raise ValueError("invalid spend or timeout bound")
    models = protocol["models"]
    if not isinstance(models, list) or len(models) != 3 or not all(isinstance(model, dict) for model in models):
        raise ValueError("Stage-7 protocol requires exactly three model records")
    ids = [model.get("variant_id") for model in models]
    if any(not isinstance(item, str) for item in ids) or len(set(ids)) != 3:
        raise ValueError("model variant IDs must be unique strings")
    if int(limits["maximum_total_requests"]) != len(models):
        raise ValueError("maximum_total_requests must equal the fixed model count")
    task = protocol["task"]
    if not isinstance(task, dict) or set(task) != {"task_id", "user_request", "expected_scene_without_seed"}:
        raise ValueError("malformed fixed task")
    return protocol


def system_prompt() -> str:
    return '''You are a constrained CARLA scene planner. Return exactly one JSON object and no Markdown.

Return only passive SceneSpec v1.1 data. Never return Python, code, tool calls, direct CARLA world coordinates, blueprint IDs, controller settings, animation fields, or any field not in this form:
{"version":"1.1","map_name":"Town01_Opt","route_id":"route_01_straight","weather_id":"clear_day","seed":1,"animal":{"type":"deer","anchor":{"route_progress_m":32.0},"trajectory":{"kind":"lateral_crossing","start_lateral_offset_m":6.0,"end_lateral_offset_m":-6.0},"speed_mps":2.0,"start_time_s":0.0}}

The shown deer type, map, route, weather, anchor, trajectory, speed and start time are the only supported values. seed must be an integer from 0 through 2147483647. The executor independently validates and resolves this JSON; it does not execute model code.'''


def user_prompt(task: dict[str, Any]) -> str:
    request = task.get("user_request")
    if not isinstance(request, str):
        raise ValueError("task user_request must be a string")
    return f"Natural-language request:\n{request}\n\nReturn only the applicable JSON object."


def connection(model: dict[str, Any], dotenv_values: dict[str, str]) -> tuple[str | None, str, str, str]:
    required = ("api_key_env", "base_url_env", "model_env", "default_base_url", "default_model", "provider")
    if any(not isinstance(model.get(key), str) for key in required):
        raise ValueError("malformed model connection configuration")
    api_key = environment_value(str(model["api_key_env"]), dotenv_values)
    base_url = environment_value(str(model["base_url_env"]), dotenv_values) or str(model["default_base_url"])
    name = environment_value(str(model["model_env"]), dotenv_values) or str(model["default_model"])
    provider = str(model["provider"])
    if provider == "openai_responses":
        url = f"{base_url.rstrip('/')}/responses"
    elif provider == "dashscope_chat_completions":
        url = f"{base_url.rstrip('/')}/chat/completions"
    else:
        raise ValueError(f"unsupported provider: {provider}")
    return api_key, name, provider, url


def response_without_seed(scene: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in scene.items() if key != "seed"}


def validate_response(text: str, expected: dict[str, Any], config: dict[str, object]) -> dict[str, object]:
    started = time.monotonic()
    try:
        scene = parse_scene_spec_json(text)
        route = load_stage7_route(PROJECT_ROOT, config, scene.route_id)
        resolved = resolve_scene_spec(scene, config, route)
        actual = response_without_seed(scene.as_dict())
        matched = actual == expected
        return {
            "status": "passed" if matched else "failed",
            "result_kind": "scene_spec",
            "instruction_fulfilled": matched,
            "instruction_mismatches": [] if matched else ["response does not exactly match the fixed verified capability"],
            "scene_spec": scene.as_dict(),
            "scene_spec_sha256": canonical_json_sha256(scene.as_dict()),
            "resolved_scene": resolved.as_dict(),
            "local_validation_s": round(time.monotonic() - started, 6),
        }
    except (SceneSpecError, ValueError) as exc:
        error = exc.as_dict() if isinstance(exc, SceneSpecError) else {"code": "local_validation_error", "message": str(exc)}
        return {"status": "failed", "result_kind": "invalid", "error": error, "local_validation_s": round(time.monotonic() - started, 6)}


def one_attempt(attempt_dir: Path, model: dict[str, Any], task: dict[str, Any], dotenv_values: dict[str, str], config: dict[str, object], limits: dict[str, Any]) -> dict[str, object]:
    api_key, model_name, provider, url = connection(model, dotenv_values)
    system, user = system_prompt(), user_prompt(task)
    body = openai_request(model_name, system, user, int(limits["max_output_tokens"])) if provider == "openai_responses" else dashscope_request(model_name, system, user, int(limits["max_output_tokens"]))
    write_json(attempt_dir / "request.json", {"variant_id": model["variant_id"], "provider": provider, "model": model_name, "url": url, "body": body, "api_key_present": api_key is not None})
    if api_key is None:
        result = {"status": "missing_api_key", "provider": provider, "model": model_name}
        write_json(attempt_dir / "attempt_result.json", result)
        return result
    try:
        status, raw, latency_s = post_json(url, api_key, body, float(limits["timeout_s"]))
        write_json(attempt_dir / "raw_response.json", raw)
        result: dict[str, object] = {"provider": provider, "model": model_name, "http_status": status, "api_latency_s": round(latency_s, 6), "reported_usage": raw.get("usage")}
        if not 200 <= status < 300:
            result["status"] = "http_error"
        else:
            text = extract_openai_response_text(raw) if provider == "openai_responses" else extract_dashscope_response_text(raw)
            write_json(attempt_dir / "response_text.json", {"response_text": text})
            validation = validate_response(text, task["expected_scene_without_seed"], config)
            write_json(attempt_dir / "local_validation.json", validation)
            if validation["result_kind"] == "scene_spec" and "scene_spec" in validation:
                write_json(attempt_dir / "scene_spec.json", validation["scene_spec"])
            result.update({"status": "passed" if validation["status"] == "passed" else "validation_failed", "result_kind": validation["result_kind"], "instruction_fulfilled": validation.get("instruction_fulfilled", False), "response_sha256": sha256_text(text), "local_validation_s": validation["local_validation_s"], "local_validation_path": "local_validation.json"})
            if validation["status"] == "passed":
                result.update({"scene_spec_path": "scene_spec.json", "scene_spec_sha256": validation["scene_spec_sha256"]})
        write_json(attempt_dir / "attempt_result.json", result)
        return result
    except (OSError, TimeoutError, ValueError, ProviderResponseError) as exc:
        result = {"status": "request_error", "provider": provider, "model": model_name, "error_type": type(exc).__name__, "error": str(exc)}
        write_json(attempt_dir / "attempt_result.json", result)
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL_PATH)
    parser.add_argument("--dotenv", type=Path, default=Path(".env"))
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    if not (run_dir / "metadata.json").is_file():
        raise SystemExit("run directory was not created by scripts/create_run.py")
    protocol_path = (PROJECT_ROOT / args.protocol).resolve() if not args.protocol.is_absolute() else args.protocol.resolve()
    protocol = load_protocol(protocol_path)
    scene_config = load_stage7_config(PROJECT_ROOT / str(protocol["scene_config"]))
    dotenv_values = load_dotenv(args.dotenv)
    write_json(run_dir / "api_protocol.json", protocol)
    write_json(run_dir / "prompt_set.json", {"prompt_version": PROMPT_VERSION, "system_prompt": system_prompt(), "task": {"task_id": protocol["task"]["task_id"], "user_prompt": user_prompt(protocol["task"])}, "provider_enforced_format": "JSON object mode plus local strict parser"})
    result: dict[str, object] = {"schema_version": 1, "protocol_id": protocol["protocol_id"], "started_at_utc": utc_now(), "request_limits": protocol["request_limits"], "planned_call_count": len(protocol["models"]), "actual_call_count": 0, "carla_started": False, "attempts": []}
    attempts = result["attempts"]
    assert isinstance(attempts, list)
    for model in protocol["models"]:
        assert isinstance(model, dict)
        attempt_dir = run_dir / "attempts" / str(model["variant_id"]) / "attempt-01"
        attempt = one_attempt(attempt_dir, model, protocol["task"], dotenv_values, scene_config, protocol["request_limits"])
        if attempt.get("status") != "missing_api_key":
            result["actual_call_count"] = int(result["actual_call_count"]) + 1
        attempts.append({"variant_id": model["variant_id"], "attempt": 1, "path": attempt_dir.relative_to(run_dir).as_posix(), "result": attempt})
    result["finished_at_utc"] = utc_now()
    result["all_first_attempts_passed"] = all(isinstance(item, dict) and isinstance(item.get("result"), dict) and item["result"].get("status") == "passed" for item in attempts)
    write_json(run_dir / "api_results.json", result)
    print(run_dir / "api_results.json")


if __name__ == "__main__":
    main()
