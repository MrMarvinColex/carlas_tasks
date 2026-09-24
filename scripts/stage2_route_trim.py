#!/usr/bin/env python3
"""Create an immutable shorter revision by slicing the approved dense chains.

No map search or simulation is needed here. The existing autopilot validator
subsequently reconstructs every waypoint and checks every edge against CARLA.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
from types import SimpleNamespace

import carla

from stage2_route_candidates import adaptive_indices, detect_turn_events
from stage2_routes import update_metadata, write_json


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stored_waypoints(document: dict) -> list:
    return [
        SimpleNamespace(transform=carla.Transform(
            carla.Location(**item["transform"]["location"]),
            carla.Rotation(**item["transform"]["rotation"]),
        ))
        for item in document["dense_reference"]["waypoints"]
    ]


def cumulative_lengths(waypoints: list) -> list[float]:
    lengths = [0.0]
    for a, b in zip(waypoints, waypoints[1:]):
        lengths.append(lengths[-1] + float(a.transform.location.distance(b.transform.location)))
    return lengths


def select_window(document: dict, number: int) -> tuple[int, int]:
    points = stored_waypoints(document)
    lengths = cumulative_lengths(points)
    if number <= 3:
        return tuple(min(range(len(points)), key=lambda i: abs(lengths[i] - fraction * lengths[-1]))
                     for fraction in (0.25, 0.75))

    events = document["turn_events"]
    policy = document["adaptive_proposal"]
    context = float(policy["turn_context_m"])
    raw = document["dense_reference"]["waypoints"]
    candidates = []
    for start in range(len(points)):
        for end in range(start + 9, len(points)):
            if raw[start]["is_junction"] or raw[end]["is_junction"]:
                continue
            kept = [e for e in events if start <= e["start_dense_index"] and end >= e["end_dense_index"]]
            if (number == 4 and len(kept) not in (1, 2)) or (number == 5 and len(kept) != 2):
                continue
            if any(not (end < e["start_dense_index"] or start > e["end_dense_index"] or e in kept) for e in events):
                continue
            if any(lengths[e["start_dense_index"]] - lengths[start] < context - 0.01
                   or lengths[end] - lengths[e["end_dense_index"]] < context - 0.01 for e in kept):
                continue
            if number == 4:
                bridge = document["bridge_crossing"]
                # Keep the entire stored crossing and enough exit road for the
                # existing <=8 m finish tolerance to stop beyond the far bank.
                if start > bridge["start_dense_index"] or end < bridge["end_dense_index"]:
                    continue
                if lengths[end] - lengths[bridge["end_dense_index"]] < 12.0 - 0.01:
                    continue
            shifted = [{**e, **{k: e[k] - start for k in
                        ("start_dense_index", "center_dense_index", "end_dense_index")}} for e in kept]
            indices = adaptive_indices(points[start:end + 1], shifted, 2.0,
                                       float(policy["straight_spacing_m"]), context)
            lower, upper = (40, 50) if number == 4 else (60, 70)
            if lower <= len(indices) <= upper:
                candidates.append((round(lengths[end] - lengths[start], 3), start, end))
    if not candidates:
        raise RuntimeError(f"no contiguous window satisfies route {number} constraints")
    _, start, end = min(candidates)
    return start, end


def trim_document(source: dict, number: int) -> tuple[dict, dict]:
    start, end = select_window(source, number)
    source_points = source["dense_reference"]["waypoints"]
    dense = [dict(item, order=i) for i, item in enumerate(source_points[start:end + 1])]
    document = copy.deepcopy(source)
    for key in ("validation", "relabelled_from_route_id", "bridge_crossing"):
        document.pop(key, None)
    document["dense_reference"]["waypoints"] = dense
    document["dense_reference"]["waypoint_count"] = len(dense)
    points = stored_waypoints(document)
    events = detect_turn_events(points)
    lengths = cumulative_lengths(points)
    policy = document["adaptive_proposal"]
    indices = adaptive_indices(points, events, 2.0, float(policy["straight_spacing_m"]), float(policy["turn_context_m"]))
    policy.update(dense_indices=indices, waypoint_count=len(indices),
                  waypoints=[dict(dense[i], order=n) for n, i in enumerate(indices)])
    target_id = source["candidate_id"]
    label = source["candidate_label"] + " (middle half)"
    if number == 4:
        target_id, label = "route_04_turn_then_bridge", "One left turn followed by the complete outer bridge crossing"
        bridge = copy.deepcopy(source["bridge_crossing"])
        bridge["start_dense_index"] -= start
        bridge["end_dense_index"] -= start
        document["bridge_crossing"] = bridge
    elif number == 5:
        target_id, label = "route_05_two_turns", "Two consecutive turns: left then right"
    document.update(
        candidate_id=target_id, candidate_label=label,
        candidate_kind="turn_then_bridge" if number == 4 else "two_turns" if number == 5 else source["candidate_kind"],
        length_m=lengths[-1], start=dense[0]["transform"]["location"], finish=dense[-1]["transform"]["location"],
        turn_events=events, status="trimmed_geometry_pending_drive_validation",
        review_status="user_requested_contiguous_shortening", autopilot_status="pending_new_start_drive_test",
        spawn_point_index_in_carla_map=None, spawn_transform=copy.deepcopy(dense[0]["transform"]),
        spawn_policy="first retained waypoint transform plus 0.35 m z, as used by spawn_at_route_start",
        trimmed_from={"route_id": source["candidate_id"], "dense_start_index": start,
                      "dense_end_index_inclusive": end, "old_length_m": source["length_m"],
                      "old_adaptive_waypoint_count": source["adaptive_proposal"]["waypoint_count"]},
    )
    checks = {
        "contiguous_source_waypoints_unchanged": all(
            {k: v for k, v in a.items() if k != "order"} == {k: v for k, v in b.items() if k != "order"}
            for a, b in zip(dense, source_points[start:end + 1])),
        "unique_dense_waypoints": len({p["waypoint_id"] for p in dense}) == len(dense),
        "length_reduced": 0 < lengths[-1] < source["length_m"],
        "adaptive_endpoints_and_order": indices == sorted(set(indices)) and indices[0] == 0 and indices[-1] == len(dense) - 1,
        "minimum_ten_working_waypoints": len(indices) >= 10,
        "turn_profile": [e["direction"] for e in events] == [[], ["left"], ["right"], ["left"], ["left", "right"]][number - 1],
    }
    if number <= 3:
        checks["middle_half_within_dense_step"] = abs(lengths[-1] - source["length_m"] / 2.0) <= 2.01
    else:
        lower, upper = (40, 50) if number == 4 else (60, 70)
        checks["requested_working_waypoint_range"] = lower <= len(indices) <= upper
        checks["start_and_finish_outside_junction"] = not dense[0]["is_junction"] and not dense[-1]["is_junction"]
    if number == 4:
        checks["full_original_bridge_retained"] = start <= source["bridge_crossing"]["start_dense_index"] and end >= source["bridge_crossing"]["end_dense_index"]
        checks["finish_beyond_bridge_with_stop_margin"] = lengths[-1] - lengths[document["bridge_crossing"]["end_dense_index"]] >= 11.99
    document["validation"] = {"status": "passed" if all(checks.values()) else "failed", "checks": checks,
                              "scope": "stored geometry checks; CARLA direct-next connectivity and actual driving tested separately"}
    return document, checks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--source-run", type=Path, default=Path("runs/20260919T154916Z-route-numbering-swap-b5e941"))
    args = parser.parse_args()
    run_dir, source_run = args.run_dir.resolve(), args.source_run.resolve()
    if not (run_dir / "metadata.json").is_file():
        raise SystemExit("create the destination with create_run.py first")
    (run_dir / "routes").mkdir(exist_ok=False)
    source_index = json.loads((source_run / "revised_routes.json").read_text())
    entries, checks, comparisons = [], {}, []
    for number, entry in enumerate(source_index["routes"], 1):
        source_path = source_run / entry["path"]
        document, route_checks = trim_document(json.loads(source_path.read_text()), number)
        document["trimmed_from"].update(source_path=str(source_path), source_sha256=sha256(source_path))
        target_id = document["candidate_id"]
        write_json(run_dir / "routes" / f"{target_id}.json", document)
        entries.append({"route_id": target_id, "path": f"routes/{target_id}.json", "label": document["candidate_label"],
                        "kind": document["candidate_kind"], "length_m": document["length_m"],
                        "adaptive_waypoint_count": document["adaptive_proposal"]["waypoint_count"],
                        "dense_waypoint_count": document["dense_reference"]["waypoint_count"],
                        "start": document["start"], "finish": document["finish"], "turn_events": document["turn_events"]})
        checks.update({f"{target_id}:{key}": value for key, value in route_checks.items()})
        comparisons.append({**document["trimmed_from"], "new_route_id": target_id,
                            "new_length_m": document["length_m"], "new_adaptive_waypoint_count": document["adaptive_proposal"]["waypoint_count"]})
    checks["exactly_five_distinct_routes"] = len(entries) == len({e["route_id"] for e in entries}) == 5
    validation = {"status": "passed" if all(checks.values()) else "failed", "checks": checks, "comparisons": comparisons,
                  "source_index_sha256": sha256(source_run / "revised_routes.json"), "generator_sha256": sha256(Path(__file__))}
    write_json(run_dir / "revised_routes.json", {"schema_version": 1, "map_name": source_index["map_name"],
               "dense_step_m": source_index["dense_step_m"], "adaptive_policy": source_index["adaptive_policy"],
               "routes": entries, "source_run": str(source_run), "trim_validation_path": "trim_validation.json"})
    write_json(run_dir / "trim_validation.json", validation)
    update_metadata(run_dir / "metadata.json", source_route_revision=str(source_run),
                    carla_client_version=version("carla"), validation_path="trim_validation.json",
                    validation_status=validation["status"], simulation_performed=False)
    print(json.dumps(validation, indent=2))
    if validation["status"] != "passed":
        raise RuntimeError("trim validation failed")


if __name__ == "__main__":
    main()
