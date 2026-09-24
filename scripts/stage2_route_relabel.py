#!/usr/bin/env python3
"""Create an immutable Stage-2 route revision with routes four and five renumbered.

The route geometry is deliberately not regenerated: this utility copies the
approved route documents into a fresh run, changes only their public route
identifiers/order, and proves that the geometry-bearing fields did not change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from stage2_routes import update_metadata, write_json


SOURCE_TO_TARGET = {
    "route_01_straight": "route_01_straight",
    "route_02_left": "route_02_left",
    "route_03_right": "route_03_right",
    "route_04_four_turns": "route_05_four_turns",
    "route_05_bridge_then_turn": "route_04_bridge_then_turn",
}
TARGET_ORDER = [
    "route_01_straight",
    "route_02_left",
    "route_03_right",
    "route_04_bridge_then_turn",
    "route_05_four_turns",
]
GEOMETRY_KEYS = ("map_name", "start", "finish", "length_m", "dense_reference", "adaptive_proposal", "turn_events")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument(
        "--source-run",
        type=Path,
        default=Path("runs/20260919T062007Z-route-revision-ca00ee"),
    )
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    source_run = args.source_run.resolve()
    metadata_path = run_dir / "metadata.json"
    source_index_path = source_run / "revised_routes.json"
    if not metadata_path.is_file():
        raise SystemExit(f"run directory was not created by create_run.py: {run_dir}")
    if not source_index_path.is_file():
        raise SystemExit(f"missing source route index: {source_index_path}")

    source_index = json.loads(source_index_path.read_text())
    source_entries = {entry["route_id"]: entry for entry in source_index["routes"]}
    if set(source_entries) != set(SOURCE_TO_TARGET):
        raise RuntimeError("source route IDs do not match the approved five-route set")

    route_dir = run_dir / "routes"
    route_dir.mkdir(parents=True, exist_ok=False)
    new_entries: list[dict[str, object]] = []
    checks: dict[str, bool] = {}
    source_files: dict[str, dict[str, str]] = {}

    for source_id, target_id in SOURCE_TO_TARGET.items():
        source_entry = source_entries[source_id]
        source_path = source_run / source_entry["path"]
        if not source_path.is_file():
            raise RuntimeError(f"missing source document: {source_path}")
        source_document = json.loads(source_path.read_text())
        if source_document["candidate_id"] != source_id:
            raise RuntimeError(f"source document ID mismatch: {source_path}")

        target_document = dict(source_document)
        target_document["candidate_id"] = target_id
        target_document["review_status"] = "user_approved_geometry_relabelled"
        target_document["relabelled_from_route_id"] = source_id
        target_document["autopilot_status"] = "not_run_under_relabelled_id"
        target_path = route_dir / f"{target_id}.json"
        write_json(target_path, target_document)
        stored_document = json.loads(target_path.read_text())
        target_check = all(
            stored_document[key] == source_document[key] for key in GEOMETRY_KEYS
        )
        checks[f"geometry_unchanged_{target_id}"] = target_check
        source_files[target_id] = {
            "source_relative_path": source_path.relative_to(source_run).as_posix(),
            "source_sha256": sha256(source_path),
            "target_relative_path": target_path.relative_to(run_dir).as_posix(),
            "target_sha256": sha256(target_path),
        }

        target_entry = dict(source_entry)
        target_entry["route_id"] = target_id
        target_entry["path"] = target_path.relative_to(run_dir).as_posix()
        target_entry["review_status"] = "user_approved_geometry_relabelled"
        target_entry["relabelled_from_route_id"] = source_id
        target_entry.pop("preview", None)
        new_entries.append(target_entry)

    ordered_entries = sorted(new_entries, key=lambda entry: TARGET_ORDER.index(entry["route_id"]))
    checks["exactly_five_routes"] = len(ordered_entries) == 5
    checks["target_order_is_expected"] = [entry["route_id"] for entry in ordered_entries] == TARGET_ORDER
    checks["only_routes_four_and_five_changed_identifiers"] = all(
        SOURCE_TO_TARGET[source_id] == target_id
        for source_id, target_id in SOURCE_TO_TARGET.items()
    )
    validation = {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "source_run": source_run.as_posix(),
        "source_index_sha256": sha256(source_index_path),
        "source_to_target_route_id": SOURCE_TO_TARGET,
        "geometry_keys_preserved": list(GEOMETRY_KEYS),
        "source_files": source_files,
        "scope": "Identifier/order relabel only; geometry and prior visual approval are inherited from the source run.",
    }
    index = {
        "schema_version": 1,
        "map_name": source_index["map_name"],
        "dense_step_m": source_index["dense_step_m"],
        "adaptive_policy": source_index["adaptive_policy"],
        "routes": ordered_entries,
        "route_numbering": {
            "reason": "User requested that the less complex bridge route become route 4 and the four-turn route become route 5.",
            "source_run": source_run.as_posix(),
            "source_to_target_route_id": SOURCE_TO_TARGET,
        },
        "validation": validation,
    }
    write_json(run_dir / "revised_routes.json", index)
    write_json(run_dir / "relabel_validation.json", validation)
    update_metadata(
        metadata_path,
        state="running",
        source_route_revision=source_run.as_posix(),
        relabel_validation_path="relabel_validation.json",
        relabel_validation_status=validation["status"],
    )
    if validation["status"] != "passed":
        raise RuntimeError("route relabel validation failed")
    print(run_dir / "revised_routes.json")


if __name__ == "__main__":
    main()
