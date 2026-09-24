#!/usr/bin/env python3
"""Build a small, explicit comparison for fixed Stage-7 API/animal replays."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def without_seed(scene: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in scene.items() if key != "seed"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-run", type=Path, required=True)
    parser.add_argument("--execution", action="append", required=True, metavar="VARIANT=RUN_DIR")
    args = parser.parse_args()
    api_run = args.api_run.resolve()
    api_results = load_object(api_run / "api_results.json")
    attempts = api_results.get("attempts")
    if not isinstance(attempts, list):
        raise RuntimeError("API result lacks attempts")
    executions: dict[str, Path] = {}
    for value in args.execution:
        variant, separator, path = value.partition("=")
        if not separator or not variant or not path or variant in executions:
            raise RuntimeError("--execution must be unique VARIANT=RUN_DIR")
        executions[variant] = Path(path).resolve()

    rows: list[dict[str, object]] = []
    scenes_without_seed: list[dict[str, object]] = []
    for attempt_entry in attempts:
        if not isinstance(attempt_entry, dict):
            raise RuntimeError("malformed attempt entry")
        variant = attempt_entry.get("variant_id")
        attempt = attempt_entry.get("result")
        if not isinstance(variant, str) or not isinstance(attempt, dict) or variant not in executions:
            raise RuntimeError("execution mapping does not match API attempts")
        execution = executions[variant]
        validation = load_object(execution / "probe_validation.json")
        scene = load_object(execution / "scene_spec.json")
        input_record = load_object(execution / "scene_input.json")
        if not validation.get("passed") or input_record.get("api_provenance", {}).get("model") != attempt.get("model"):
            raise RuntimeError(f"execution provenance or validation failed for {variant}")
        motion = validation.get("motion")
        if not isinstance(motion, dict):
            raise RuntimeError(f"motion summary missing for {variant}")
        semantic_delta = validation.get("semantic_support_delta_from_baseline_pixels")
        if not isinstance(semantic_delta, list) or not semantic_delta:
            raise RuntimeError(f"semantic visibility summary missing for {variant}")
        scenes_without_seed.append(without_seed(scene))
        rows.append(
            {
                "variant_id": variant,
                "provider": attempt.get("provider"),
                "model": attempt.get("model"),
                "api_latency_s": attempt.get("api_latency_s"),
                "local_validation_s": attempt.get("local_validation_s"),
                "reported_usage": attempt.get("reported_usage"),
                "scene_spec_sha256": attempt.get("scene_spec_sha256"),
                "seed": scene.get("seed"),
                "execution_run": execution.name,
                "probe_passed": validation.get("passed"),
                "semantic_dynamic_delta_min_pixels": min(int(value) for value in semantic_delta),
                "semantic_dynamic_delta_max_pixels": max(int(value) for value in semantic_delta),
                "total_sensor_motion_m": motion.get("total_sensor_motion_m"),
                "maximum_commanded_step_m": motion.get("maximum_commanded_per_tick_step_m"),
                "endpoint_error_m": motion.get("distance_to_configured_endpoint_m"),
                "collision_with_deer": validation.get("collision_with_deer"),
            }
        )
    if set(executions) != {row["variant_id"] for row in rows}:
        raise RuntimeError("an execution was supplied without a matching API attempt")
    comparison = {
        "schema_version": 1,
        "protocol_id": api_results.get("protocol_id"),
        "comparison_scope": "one identical first-attempt API request and one grounded front-centre replay per variant",
        "all_api_first_attempts_passed": api_results.get("all_first_attempts_passed"),
        "all_scene_specs_match_except_seed": all(scene == scenes_without_seed[0] for scene in scenes_without_seed[1:]),
        "rows": rows,
        "limitations": [
            "The policy deliberately offers one verified animal capability, so acceptance measures protocol compliance rather than open-ended scene creativity.",
            "The front-centre probe is asset/effect evidence; it is not the full 18-sensor edited-drive dataset.",
            "Direct collision evidence does not establish Traffic Manager braking.",
        ],
    }
    write_json(api_run / "stage7_comparison.json", comparison)
    print(api_run / "stage7_comparison.json")


if __name__ == "__main__":
    main()
