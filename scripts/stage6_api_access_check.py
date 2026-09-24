#!/usr/bin/env python3
"""Perform a zero-inference Stage-6 API-access check without logging secrets.

The check reads API keys only from a local ``.env`` file or the process
environment.  It makes authenticated ``GET /models`` requests; it never sends
a prompt or creates a model response.  Results contain endpoints, HTTP status,
latency, and model identifiers only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
DASHSCOPE_MODEL_LIST_URLS = {
    "singapore": "https://dashscope-intl.aliyuncs.com/api/v1/models?providers=qwen&page_no=1&page_size=200",
    "beijing": "https://dashscope.aliyuncs.com/api/v1/models?providers=qwen&page_no=1&page_size=200",
    "virginia": "https://dashscope-us.aliyuncs.com/api/v1/models?providers=qwen&page_no=1&page_size=200",
    "hong_kong": "https://cn-hongkong.dashscope.aliyuncs.com/api/v1/models?providers=qwen&page_no=1&page_size=200",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_dotenv(path: Path) -> dict[str, str]:
    """Read simple KEY=VALUE settings without printing their values."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{line_number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"{path}:{line_number}: empty key")
        values[key] = value.strip().strip("\"'")
    return values


def environment_value(name: str, dotenv_values: dict[str, str]) -> str | None:
    value = os.environ.get(name) or dotenv_values.get(name)
    return value if value else None


def request_json(url: str, api_key: str, timeout_s: float) -> dict[str, object]:
    """Call a model-list endpoint and retain no response body on failure."""
    started = time.monotonic()
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = response.read()
            status = int(response.status)
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("model-list response is not a JSON object")
        return {
            "status": "authenticated" if 200 <= status < 300 else "unexpected_http_status",
            "http_status": status,
            "latency_s": round(time.monotonic() - started, 3),
            "payload": payload,
        }
    except urllib.error.HTTPError as exc:
        return {
            "status": "http_error",
            "http_status": int(exc.code),
            "latency_s": round(time.monotonic() - started, 3),
        }
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        return {
            "status": "request_error",
            "error_type": type(exc).__name__,
            "latency_s": round(time.monotonic() - started, 3),
        }


def model_ids(payload: dict[str, Any]) -> list[str]:
    """Extract identifiers from OpenAI and Model Studio model-list responses."""
    items = payload.get("data")
    id_fields = ("id",)
    if not isinstance(items, list):
        output = payload.get("output")
        items = output.get("models") if isinstance(output, dict) else None
        id_fields = ("model", "id")
    if not isinstance(items, list):
        return []

    identifiers: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        for field in id_fields:
            value = item.get(field)
            if isinstance(value, str) and value:
                identifiers.add(value)
                break
    return sorted(identifiers)


def summarize_result(url: str, response: dict[str, object]) -> dict[str, object]:
    payload = response.pop("payload", None)
    summary: dict[str, object] = {"url": url, **response}
    if isinstance(payload, dict):
        ids = model_ids(payload)
        summary.update(
            {
                "model_count": len(ids),
                "model_ids": ids,
                "contains_gpt_6_astra": "gpt-6-astra" in ids,
            }
        )
    return summary


def check_dashscope(api_key: str, timeout_s: float, region: str) -> dict[str, object]:
    regions = list(DASHSCOPE_MODEL_LIST_URLS) if region == "auto" else [region]
    attempts: list[dict[str, object]] = []
    for candidate in regions:
        url = DASHSCOPE_MODEL_LIST_URLS[candidate]
        summary = summarize_result(url, request_json(url, api_key, timeout_s))
        summary["region"] = candidate
        attempts.append(summary)
        if summary["status"] == "authenticated":
            return {"status": "authenticated", "selected_region": candidate, "attempts": attempts}
    return {"status": "not_authenticated", "selected_region": None, "attempts": attempts}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--dotenv", type=Path, default=Path(".env"))
    parser.add_argument("--timeout-s", type=float, default=15.0)
    parser.add_argument("--dashscope-region", choices=["auto", *DASHSCOPE_MODEL_LIST_URLS], default="auto")
    args = parser.parse_args()
    if args.timeout_s <= 0.0:
        raise SystemExit("--timeout-s must be positive")
    run_dir = args.run_dir.resolve()
    if not (run_dir / "metadata.json").is_file():
        raise SystemExit("run directory was not created by scripts/create_run.py")

    dotenv_values = load_dotenv(args.dotenv)
    openai_key = environment_value("OPENAI_API_KEY", dotenv_values)
    dashscope_key = environment_value("DASHSCOPE_API_KEY", dotenv_values)
    result: dict[str, object] = {
        "schema_version": 1,
        "checked_at_utc": utc_now(),
        "test_kind": "authenticated_model_list_only",
        "text_generation_requested": False,
        "dotenv_path": args.dotenv.as_posix(),
        "providers": {},
    }
    providers = result["providers"]
    assert isinstance(providers, dict)
    if openai_key is None:
        providers["openai"] = {"status": "missing_api_key", "url": OPENAI_MODELS_URL}
    else:
        providers["openai"] = summarize_result(OPENAI_MODELS_URL, request_json(OPENAI_MODELS_URL, openai_key, args.timeout_s))
    if dashscope_key is None:
        providers["dashscope"] = {"status": "missing_api_key", "requested_region": args.dashscope_region}
    else:
        providers["dashscope"] = check_dashscope(dashscope_key, args.timeout_s, args.dashscope_region)

    statuses = [str(item.get("status")) for item in providers.values() if isinstance(item, dict)]
    result["status"] = "passed" if statuses == ["authenticated", "authenticated"] else "failed"
    output_path = run_dir / "api_access_check.json"
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(output_path)
    if result["status"] != "passed":
        raise SystemExit("one or more API access checks did not authenticate")


if __name__ == "__main__":
    main()
