#!/usr/bin/env python3
"""Run the fixed, spend-bounded Stage-6 API protocol without starting CARLA.

The adapter owns one provider-neutral attempt format.  It sends only the
three checked prompts from ``configs/stage6_api_protocol.json``, preserves each
sanitized request/raw response/extracted JSON response, and validates the
response locally before an executor can use it.  It never runs model-produced
code and it never writes an API key into the run directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
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
from stage6_scene_spec import (
    Refusal,
    SceneSpec,
    SceneSpecError,
    canonical_json_sha256,
    load_route_geometry,
    load_stage6_config,
    parse_response_json,
    resolve_scene_spec,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL_PATH = Path("configs/stage6_api_protocol.json")
PROMPT_VERSION = "stage6-straight-pilot-v1"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object in {path}")
    return value


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_protocol(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("Stage-6 API protocol must be a schema_version=1 JSON object")
    for key in ("protocol_id", "scene_config", "request_limits", "models", "tasks"):
        if key not in value:
            raise ValueError(f"Stage-6 API protocol misses {key!r}")
    if not isinstance(value["models"], list) or not value["models"]:
        raise ValueError("Stage-6 API protocol needs at least one model")
    if not isinstance(value["tasks"], list) or not value["tasks"]:
        raise ValueError("Stage-6 API protocol needs at least one task")
    limits = value["request_limits"]
    if not isinstance(limits, dict):
        raise ValueError("request_limits must be an object")
    required_limits = ("repeat_count", "retry_count", "timeout_s", "max_output_tokens", "maximum_total_requests")
    if any(key not in limits for key in required_limits):
        raise ValueError("request_limits is incomplete")
    if int(limits["repeat_count"]) != 1 or int(limits["retry_count"]) < 0:
        raise ValueError("this initial protocol permits exactly one repeat and non-negative retries")
    if not 16 <= int(limits["max_output_tokens"]) <= 256:
        raise ValueError("max_output_tokens must stay within the 16..256 spend-bound")
    if float(limits["timeout_s"]) <= 0.0 or int(limits["maximum_total_requests"]) <= 0:
        raise ValueError("timeout_s and maximum_total_requests must be positive")
    model_ids = [item.get("variant_id") for item in value["models"] if isinstance(item, dict)]
    task_ids = [item.get("task_id") for item in value["tasks"] if isinstance(item, dict)]
    if any(not isinstance(item, str) for item in model_ids) or len(set(model_ids)) != len(model_ids):
        raise ValueError("model variant_id values must be unique strings")
    if any(not isinstance(item, str) for item in task_ids) or len(set(task_ids)) != len(task_ids):
        raise ValueError("task_id values must be unique strings")
    return value


def system_prompt() -> str:
    return """You are a constrained CARLA scene planner. Return exactly one JSON object and no Markdown.

You can only describe passive SceneSpec data for a fixed executor. Never return Python, code, tool calls, direct CARLA world coordinates, or fields outside the listed JSON forms.

Supported SceneSpec form:
{"version":"1.0","map_name":"Town01_Opt","route_id":"route_01_straight","weather_id":"clear_day or wet_cloudy_day","seed":1,"edits":[{"operation":"spawn_parked_vehicle","blueprint_id":"vehicle.audi.a2","anchor":{"route_progress_m":40.0,"side":"left"},"longitudinal_offset_m":0.0,"lateral_offset_m":10.0}]}

Only one to three static vehicle.audi.a2 edits are supported. An anchor needs route_progress_m from 20 through 95, side "left", longitudinal_offset_m from -10 through 10, and lateral_offset_m from 5 through 10. A seed is an integer from 0 through 2147483647.

Animals, moving actors, behavior, route changes, custom assets, and traffic reactions are unsupported. If a request needs any unsupported capability, return only this refusal form:
{"version":"1.0","refusal":{"code":"unsupported_capability","requested_capabilities":["moving_animal"],"message":"brief factual reason"}}
"""


def user_prompt(task: dict[str, Any]) -> str:
    request = task.get("user_request")
    if not isinstance(request, str):
        raise ValueError("task user_request must be a string")
    return f"Natural-language request:\n{request}\n\nReturn only the applicable JSON object."


def openai_request(model: str, system: str, user: str, max_output_tokens: int) -> dict[str, object]:
    return {
        "model": model,
        "input": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_output_tokens": max_output_tokens,
        "store": False,
        "text": {"format": {"type": "json_object"}},
    }


def dashscope_request(model: str, system: str, user: str, max_output_tokens: int) -> dict[str, object]:
    return {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": max_output_tokens,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "enable_thinking": False,
    }


def floats_equal(first: object, second: object) -> bool:
    return isinstance(first, (int, float)) and not isinstance(first, bool) and isinstance(second, (int, float)) and not isinstance(second, bool) and math.isclose(float(first), float(second), rel_tol=0.0, abs_tol=1e-6)


def scene_matches_task(scene: SceneSpec, expected: dict[str, Any]) -> dict[str, object]:
    mismatches: list[str] = []
    for key in ("map_name", "route_id", "weather_id"):
        if scene.as_dict().get(key) != expected.get(key):
            mismatches.append(f"{key}: expected {expected.get(key)!r}, got {scene.as_dict().get(key)!r}")
    expected_edits = expected.get("edits")
    if not isinstance(expected_edits, list):
        return {"passed": False, "mismatches": ["protocol expected_scene.edits is malformed"]}
    if len(scene.edits) != len(expected_edits):
        mismatches.append(f"edit count: expected {len(expected_edits)}, got {len(scene.edits)}")
    for index, (edit, expected_edit) in enumerate(zip(scene.edits, expected_edits)):
        if not isinstance(expected_edit, dict):
            mismatches.append(f"edits[{index}] protocol record is malformed")
            continue
        actual = {
            "blueprint_id": edit.blueprint_id,
            "route_progress_m": edit.anchor.route_progress_m,
            "side": edit.anchor.side,
            "longitudinal_offset_m": edit.longitudinal_offset_m,
            "lateral_offset_m": edit.lateral_offset_m,
        }
        for key, expected_value in expected_edit.items():
            actual_value = actual.get(key)
            if isinstance(expected_value, (int, float)) and not isinstance(expected_value, bool):
                same = floats_equal(actual_value, expected_value)
            else:
                same = actual_value == expected_value
            if not same:
                mismatches.append(f"edits[{index}].{key}: expected {expected_value!r}, got {actual_value!r}")
    return {"passed": not mismatches, "mismatches": mismatches}


def validate_model_response(response_text: str, task: dict[str, Any], scene_config: dict[str, object]) -> dict[str, object]:
    """Validate syntax, executor policy, and the fixed request's intended outcome."""
    started = time.monotonic()
    try:
        response = parse_response_json(response_text)
        expected_kind = task.get("expected_kind")
        if isinstance(response, Refusal):
            expected = task.get("expected_refusal")
            if expected_kind != "refusal" or not isinstance(expected, dict):
                return {
                    "status": "failed",
                    "result_kind": "refusal",
                    "error": {"code": "unexpected_refusal", "message": "task requires a SceneSpec, not a refusal"},
                    "local_validation_s": round(time.monotonic() - started, 6),
                }
            expected_capability = expected.get("requested_capability")
            fulfilled = (
                response.code == expected.get("code")
                and isinstance(expected_capability, str)
                and expected_capability in response.requested_capabilities
            )
            return {
                "status": "passed" if fulfilled else "failed",
                "result_kind": "refusal",
                "refusal": response.as_dict(),
                "instruction_fulfilled": fulfilled,
                "local_validation_s": round(time.monotonic() - started, 6),
            }
        if expected_kind != "scene_spec":
            return {
                "status": "failed",
                "result_kind": "scene_spec",
                "error": {"code": "unexpected_scene_spec", "message": "task requires a structured refusal"},
                "local_validation_s": round(time.monotonic() - started, 6),
            }
        route = load_route_geometry(PROJECT_ROOT, scene_config, response.route_id)
        resolved = resolve_scene_spec(response, scene_config, route)
        expected_scene = task.get("expected_scene")
        if not isinstance(expected_scene, dict):
            raise ValueError("scene task has malformed expected_scene")
        match = scene_matches_task(response, expected_scene)
        return {
            "status": "passed" if match["passed"] else "failed",
            "result_kind": "scene_spec",
            "scene_spec": response.as_dict(),
            "scene_spec_sha256": canonical_json_sha256(response.as_dict()),
            "resolved_scene": resolved.as_dict(),
            "instruction_fulfilled": bool(match["passed"]),
            "instruction_mismatches": match["mismatches"],
            "local_validation_s": round(time.monotonic() - started, 6),
        }
    except (SceneSpecError, ValueError) as exc:
        error = exc.as_dict() if isinstance(exc, SceneSpecError) else {"code": "local_validation_error", "message": str(exc)}
        return {
            "status": "failed",
            "result_kind": "invalid",
            "error": error,
            "local_validation_s": round(time.monotonic() - started, 6),
        }


def variant_connection(variant: dict[str, Any], dotenv_values: dict[str, str]) -> tuple[str | None, str, str, str]:
    api_key_name = variant.get("api_key_env")
    base_url_name = variant.get("base_url_env")
    model_name = variant.get("model_env")
    if not all(isinstance(value, str) for value in (api_key_name, base_url_name, model_name)):
        raise ValueError("model variant environment configuration is malformed")
    api_key = environment_value(api_key_name, dotenv_values)
    base_url = environment_value(base_url_name, dotenv_values) or str(variant["default_base_url"])
    model = environment_value(model_name, dotenv_values) or str(variant["default_model"])
    provider = str(variant["provider"])
    if provider == "openai_responses":
        url = f"{base_url.rstrip('/')}/responses"
    elif provider == "dashscope_chat_completions":
        url = f"{base_url.rstrip('/')}/chat/completions"
    else:
        raise ValueError(f"unsupported provider adapter {provider!r}")
    return api_key, model, provider, url


def one_attempt(
    attempt_dir: Path,
    variant: dict[str, Any],
    task: dict[str, Any],
    dotenv_values: dict[str, str],
    scene_config: dict[str, object],
    max_output_tokens: int,
    timeout_s: float,
) -> dict[str, object]:
    """Perform exactly one call and persist all non-secret evidence for it."""
    api_key, model, provider, url = variant_connection(variant, dotenv_values)
    system, user = system_prompt(), user_prompt(task)
    if provider == "openai_responses":
        body = openai_request(model, system, user, max_output_tokens)
    else:
        body = dashscope_request(model, system, user, max_output_tokens)
    request_record = {
        "variant_id": variant["variant_id"],
        "provider": provider,
        "model": model,
        "url": url,
        "body": body,
        "api_key_present": api_key is not None,
    }
    write_json(attempt_dir / "request.json", request_record)
    if api_key is None:
        result = {"status": "missing_api_key", "provider": provider, "model": model}
        write_json(attempt_dir / "attempt_result.json", result)
        return result
    try:
        http_status, raw_response, api_latency_s = post_json(url, api_key, body, timeout_s)
        write_json(attempt_dir / "raw_response.json", raw_response)
        result: dict[str, object] = {
            "provider": provider,
            "model": model,
            "http_status": http_status,
            "api_latency_s": round(api_latency_s, 6),
            "reported_usage": raw_response.get("usage"),
        }
        if not 200 <= http_status < 300:
            result["status"] = "http_error"
            write_json(attempt_dir / "attempt_result.json", result)
            return result
        response_text = extract_openai_response_text(raw_response) if provider == "openai_responses" else extract_dashscope_response_text(raw_response)
        write_json(attempt_dir / "response_text.json", {"response_text": response_text})
        validation = validate_model_response(response_text, task, scene_config)
        write_json(attempt_dir / "local_validation.json", validation)
        if validation["result_kind"] == "scene_spec" and "scene_spec" in validation:
            write_json(attempt_dir / "scene_spec.json", validation["scene_spec"])
        elif validation["result_kind"] == "refusal" and "refusal" in validation:
            write_json(attempt_dir / "refusal.json", validation["refusal"])
        result.update(
            {
                "status": "passed" if validation["status"] == "passed" else "validation_failed",
                "result_kind": validation["result_kind"],
                "instruction_fulfilled": validation.get("instruction_fulfilled", False),
                "response_sha256": sha256_text(response_text),
                "local_validation_s": validation["local_validation_s"],
                "local_validation_path": "local_validation.json",
            }
        )
        if validation["result_kind"] == "scene_spec" and validation["status"] == "passed":
            result["scene_spec_path"] = "scene_spec.json"
            result["scene_spec_sha256"] = validation["scene_spec_sha256"]
        if validation["result_kind"] == "refusal" and validation["status"] == "passed":
            result["refusal_path"] = "refusal.json"
        write_json(attempt_dir / "attempt_result.json", result)
        return result
    except (OSError, TimeoutError, ValueError, ProviderResponseError) as exc:
        result = {
            "status": "request_error",
            "provider": provider,
            "model": model,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        write_json(attempt_dir / "attempt_result.json", result)
        return result


def select_records(records: list[dict[str, Any]], selected_ids: list[str] | None, id_key: str) -> list[dict[str, Any]]:
    available = {str(item[id_key]): item for item in records}
    if selected_ids is None:
        return list(records)
    missing = [item for item in selected_ids if item not in available]
    if missing:
        raise ValueError(f"unknown {id_key} value(s): {', '.join(missing)}")
    return [available[item] for item in selected_ids]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL_PATH)
    parser.add_argument("--dotenv", type=Path, default=Path(".env"))
    parser.add_argument("--variants", nargs="+", help="variant_id values; default is every protocol variant")
    parser.add_argument("--tasks", nargs="+", help="task_id values; default is every protocol task")
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    if not (run_dir / "metadata.json").is_file():
        raise SystemExit("run directory was not created by scripts/create_run.py")
    protocol_path = (PROJECT_ROOT / args.protocol).resolve() if not args.protocol.is_absolute() else args.protocol.resolve()
    protocol = load_protocol(protocol_path)
    variants = select_records(protocol["models"], args.variants, "variant_id")
    tasks = select_records(protocol["tasks"], args.tasks, "task_id")
    limits = protocol["request_limits"]
    assert isinstance(limits, dict)
    maximum_calls = len(variants) * len(tasks) * (int(limits["retry_count"]) + 1)
    if maximum_calls > int(limits["maximum_total_requests"]):
        raise SystemExit(f"protocol would make {maximum_calls} calls; maximum_total_requests is {limits['maximum_total_requests']}")
    scene_config_path = PROJECT_ROOT / str(protocol["scene_config"])
    scene_config = load_stage6_config(scene_config_path)
    dotenv_values = load_dotenv(args.dotenv)
    copied_protocol = run_dir / "api_protocol.json"
    write_json(copied_protocol, protocol)
    write_json(
        run_dir / "prompt_set.json",
        {
            "prompt_version": PROMPT_VERSION,
            "system_prompt": system_prompt(),
            "tasks": [{"task_id": task["task_id"], "user_prompt": user_prompt(task)} for task in tasks],
            "provider_enforced_format": "JSON object mode; project-local strict parser and task matcher are the execution boundary",
        },
    )
    result: dict[str, object] = {
        "schema_version": 1,
        "protocol_id": protocol["protocol_id"],
        "started_at_utc": utc_now(),
        "request_limits": limits,
        "planned_call_count": maximum_calls,
        "actual_call_count": 0,
        "carla_started": False,
        "attempts": [],
    }
    attempts = result["attempts"]
    assert isinstance(attempts, list)
    for variant in variants:
        for task in tasks:
            relative = Path("attempts") / str(variant["variant_id"]) / str(task["task_id"]) / "attempt-01"
            attempt_dir = run_dir / relative
            existing_result = attempt_dir / "attempt_result.json"
            if existing_result.is_file():
                attempt = load_json_object(existing_result)
                resumed_existing = True
            else:
                attempt = one_attempt(
                    attempt_dir,
                    variant,
                    task,
                    dotenv_values,
                    scene_config,
                    int(limits["max_output_tokens"]),
                    float(limits["timeout_s"]),
                )
                resumed_existing = False
            if attempt.get("status") != "missing_api_key":
                result["actual_call_count"] = int(result["actual_call_count"]) + 1
            attempts.append(
                {
                    "variant_id": variant["variant_id"],
                    "task_id": task["task_id"],
                    "attempt": 1,
                    "attempt_directory": relative.as_posix(),
                    "resumed_existing_attempt": resumed_existing,
                    **attempt,
                }
            )
    statuses = [item.get("status") for item in attempts]
    result["finished_at_utc"] = utc_now()
    result["status"] = "passed" if statuses and all(status == "passed" for status in statuses) else "incomplete_or_failed"
    write_json(run_dir / "api_protocol_result.json", result)
    print(run_dir / "api_protocol_result.json")
    if result["status"] != "passed":
        raise SystemExit("one or more fixed protocol attempts did not pass")


if __name__ == "__main__":
    main()
