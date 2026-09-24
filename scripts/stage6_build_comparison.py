#!/usr/bin/env python3
"""Build the Stage-6 comparison table from saved API and CARLA artifacts.

No provider is contacted and CARLA is not started.  The generated table keeps
first-attempt API success distinct from scene execution, and leaves cost as
not calculated when no dated provider price record is stored in the run.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def usage_counts(usage: object) -> tuple[int | None, int | None, int | None]:
    """Normalise the two provider usage spellings without inventing values."""
    if not isinstance(usage, dict):
        return None, None, None

    def number(*keys: str) -> int | None:
        for key in keys:
            value = usage.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                return value
        return None

    return (
        number("input_tokens", "prompt_tokens"),
        number("output_tokens", "completion_tokens"),
        number("total_tokens"),
    )


def passed_route_and_camera(execution: dict[str, Any]) -> tuple[bool | None, bool | None]:
    if execution.get("status") != "passed":
        return False, False
    route = execution.get("route_check")
    camera = execution.get("camera_validation")
    route_ok = isinstance(route, dict) and isinstance(route.get("checks"), dict) and all(route["checks"].values())
    camera_ok = isinstance(camera, dict) and camera.get("status") == "passed"
    return route_ok, camera_ok


def find_execution_records(runs_dir: Path, wanted_sources: set[str]) -> dict[str, list[tuple[Path, dict[str, Any]]]]:
    found: dict[str, list[tuple[Path, dict[str, Any]]]] = {source: [] for source in wanted_sources}
    for path in sorted(runs_dir.glob("*/execution_result.json")):
        try:
            execution = read_json_object(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        provenance = execution.get("api_provenance")
        if not isinstance(provenance, dict):
            continue
        source = provenance.get("source_attempt_result_path")
        if not isinstance(source, str):
            continue
        source_key = str(Path(source).resolve())
        if source_key in found:
            found[source_key].append((path, execution))
    return found


def row_from_attempt(attempt: dict[str, Any], executions: list[tuple[Path, dict[str, Any]]]) -> dict[str, object]:
    usage = attempt.get("reported_usage")
    input_tokens, output_tokens, total_tokens = usage_counts(usage)
    result_kind = attempt.get("result_kind")
    row: dict[str, object] = {
        "variant_id": attempt.get("variant_id"),
        "provider": attempt.get("provider"),
        "model": attempt.get("model"),
        "task_id": attempt.get("task_id"),
        "attempt": attempt.get("attempt"),
        "first_attempt_status": attempt.get("status"),
        "schema_and_task_valid": attempt.get("status") == "passed",
        "instruction_fulfilled": attempt.get("instruction_fulfilled"),
        "result_kind": result_kind,
        "api_latency_s": attempt.get("api_latency_s"),
        "local_validation_s": attempt.get("local_validation_s"),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost": None,
        "cost_status": "not_calculated_no_dated_provider_price_record",
        "api_attempt_directory": attempt.get("attempt_directory"),
        "execution_run_ids": [],
        "execution_status": "not_applicable_correct_refusal" if result_kind == "refusal" and attempt.get("status") == "passed" else "not_run",
        "carla_application_and_validation_wall_s": None,
        "route_completed": None,
        "camera_validation_passed": None,
        "visibility_passed": None,
    }
    if result_kind != "scene_spec":
        return row
    row["execution_run_ids"] = [path.parent.name for path, _ in executions]
    passed = [(path, execution) for path, execution in executions if execution.get("status") == "passed"]
    if not passed:
        row["execution_status"] = "not_run" if not executions else "no_passing_execution"
        return row
    # The protocol executes exactly one saved scene per model/task.  Keeping all
    # discovered IDs makes an accidental extra replay visible instead of hidden.
    execution_path, execution = passed[0]
    timing = execution.get("timing")
    route_ok, camera_ok = passed_route_and_camera(execution)
    row.update(
        {
            "execution_status": "passed" if len(passed) == 1 else "passed_with_additional_replays_recorded",
            "selected_execution_run_id": execution_path.parent.name,
            "carla_application_and_validation_wall_s": (
                timing.get("carla_application_and_validation_wall_s") if isinstance(timing, dict) else None
            ),
            "route_completed": route_ok,
            "camera_validation_passed": camera_ok,
            "visibility_passed": execution.get("visibility_passed"),
        }
    )
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-run-dir", type=Path, required=True)
    parser.add_argument("--runs-dir", type=Path, default=Path("runs"))
    args = parser.parse_args()
    api_run_dir = args.api_run_dir.resolve()
    protocol = read_json_object(api_run_dir / "api_protocol_result.json")
    attempts = protocol.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        raise SystemExit("api_protocol_result.json has no attempts")
    source_by_index: dict[int, str] = {}
    for index, attempt in enumerate(attempts):
        if not isinstance(attempt, dict):
            raise SystemExit(f"attempt {index} is malformed")
        source_by_index[index] = str((api_run_dir / str(attempt["attempt_directory"]) / "attempt_result.json").resolve())
    execution_records = find_execution_records(args.runs_dir.resolve(), set(source_by_index.values()))
    rows = [row_from_attempt(attempt, execution_records[source_by_index[index]]) for index, attempt in enumerate(attempts)]
    complete_scenes = [row for row in rows if row["result_kind"] == "scene_spec"]
    correct_refusals = [row for row in rows if row["execution_status"] == "not_applicable_correct_refusal"]
    result = {
        "schema_version": 1,
        "protocol_id": protocol.get("protocol_id"),
        "api_run_id": api_run_dir.name,
        "cost_policy": "not calculated because no dated provider price record was retrieved or stored",
        "summary": {
            "planned_calls": protocol.get("planned_call_count"),
            "recorded_calls": protocol.get("actual_call_count"),
            "first_attempt_passes": sum(row["first_attempt_status"] == "passed" for row in rows),
            "first_attempt_total": len(rows),
            "scene_specs": len(complete_scenes),
            "scene_specs_with_passing_carla_execution": sum(
                isinstance(row["execution_status"], str) and row["execution_status"].startswith("passed")
                for row in complete_scenes
            ),
            "correct_structured_refusals": len(correct_refusals),
        },
        "rows": rows,
    }
    json_path = api_run_dir / "stage6_comparison.json"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    csv_path = api_run_dir / "stage6_comparison.csv"
    fieldnames = [
        "variant_id", "provider", "model", "task_id", "attempt", "first_attempt_status", "schema_and_task_valid",
        "instruction_fulfilled", "result_kind", "api_latency_s", "local_validation_s", "input_tokens", "output_tokens",
        "total_tokens", "cost", "cost_status", "execution_status", "selected_execution_run_id",
        "carla_application_and_validation_wall_s", "route_completed", "camera_validation_passed", "visibility_passed",
        "api_attempt_directory", "execution_run_ids",
    ]
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            flat = dict(row)
            flat["execution_run_ids"] = ";".join(str(value) for value in row["execution_run_ids"])
            writer.writerow(flat)
    print(json_path)
    print(csv_path)


if __name__ == "__main__":
    main()
