#!/usr/bin/env python3
"""Generate a visual-only set of diverse Town01_Opt route candidates.

This probe does not replace the adopted Stage-2 routes.  It searches native
spawn anchors for five deliberately different geometries, keeps a dense 2 m
reference path for connectivity, and proposes an adaptive waypoint subset:
roughly 10 m on straights and 2 m near actual heading-change events.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import carla

from stage2_routes import (
    PNG_SIGNATURE,
    ROUTE_COLORS,
    SelectedRoute,
    canonical_transform,
    capture_topdown_overview,
    configure_synchronous_world,
    hide_road_lines,
    location_to_dict,
    make_connected_route,
    restore_world_settings,
    route_length_m,
    short_map_name,
    transform_to_dict,
    update_metadata,
    waypoint_sort_key,
    waypoint_to_dict,
    write_json,
)


@dataclass
class Candidate:
    kind: str
    label: str
    route: SelectedRoute
    turn_events: list[dict[str, object]]
    adaptive_indices: list[int]
    dense_length_m: float


def normalize_degrees(angle: float) -> float:
    return (angle + 180.0) % 360.0 - 180.0


def detect_turn_events(waypoints: list[carla.Waypoint]) -> list[dict[str, object]]:
    """Cluster sustained heading changes into human-readable turn events."""
    edge_changes = [
        normalize_degrees(
            float(second.transform.rotation.yaw) - float(first.transform.rotation.yaw)
        )
        for first, second in zip(waypoints, waypoints[1:])
    ]
    active_edges = [index for index, change in enumerate(edge_changes) if abs(change) >= 0.75]
    if not active_edges:
        return []

    clusters: list[list[int]] = [[active_edges[0]]]
    for edge_index in active_edges[1:]:
        if edge_index - clusters[-1][-1] <= 3:
            clusters[-1].append(edge_index)
        else:
            clusters.append([edge_index])

    events: list[dict[str, object]] = []
    for cluster in clusters:
        start_edge = max(0, cluster[0] - 1)
        end_edge = min(len(edge_changes) - 1, cluster[-1] + 1)
        signed_change = sum(edge_changes[start_edge : end_edge + 1])
        if abs(signed_change) < 30.0:
            continue
        center_index = (start_edge + end_edge + 1) // 2
        # CARLA uses a left-handed world: positive yaw turns toward +Y and is
        # a right turn from +X; negative yaw is a left turn.
        direction = "right" if signed_change > 0.0 else "left"
        events.append(
            {
                "direction": direction,
                "signed_heading_change_deg": signed_change,
                "start_dense_index": start_edge,
                "center_dense_index": center_index,
                "end_dense_index": end_edge + 1,
                "progress_fraction": center_index / max(1, len(waypoints) - 1),
                "location": location_to_dict(waypoints[center_index].transform.location),
            }
        )
    return events


def adaptive_indices(
    waypoints: list[carla.Waypoint],
    turn_events: list[dict[str, object]],
    dense_step_m: float,
    straight_spacing_m: float,
    turn_context_m: float,
) -> list[int]:
    """Keep dense points near manoeuvres and sparse anchors on straights."""
    context_steps = max(1, math.ceil(turn_context_m / dense_step_m))
    dense_zone: set[int] = set()
    for event in turn_events:
        start = max(0, int(event["start_dense_index"]) - context_steps)
        end = min(len(waypoints) - 1, int(event["end_dense_index"]) + context_steps)
        dense_zone.update(range(start, end + 1))
    selected = [0]
    last_kept = 0
    for index in range(1, len(waypoints) - 1):
        if index in dense_zone:
            selected.append(index)
            last_kept = index
            continue
        distance = waypoints[last_kept].transform.location.distance(waypoints[index].transform.location)
        if distance >= straight_spacing_m - 0.05:
            selected.append(index)
            last_kept = index
    if selected[-1] != len(waypoints) - 1:
        selected.append(len(waypoints) - 1)
    return sorted(set(selected))


def route_prefix(route: SelectedRoute, point_count: int) -> SelectedRoute:
    return SelectedRoute(
        route_id="",
        spawn_index=route.spawn_index,
        spawn_transform=route.spawn_transform,
        branch_seed=route.branch_seed,
        waypoints=route.waypoints[:point_count],
        branch_choices=route.branch_choices[: max(0, point_count - 1)],
    )


def category_matches(kind: str, events: list[dict[str, object]]) -> bool:
    middle_events = [
        event for event in events if 0.18 <= float(event["progress_fraction"]) <= 0.78
    ]
    directions = [str(event["direction"]) for event in middle_events]
    if kind == "straight":
        return len(events) == 0
    if kind == "left":
        return len(events) == 1 and len(middle_events) == 1 and directions == ["left"]
    if kind == "right":
        return len(events) == 1 and len(middle_events) == 1 and directions == ["right"]
    if kind == "zigzag":
        return len(events) in (2, 3) and "left" in directions and "right" in directions
    if kind == "complex":
        return len(events) >= 3 and len(middle_events) >= 2
    raise ValueError(kind)


def route_bins(route: SelectedRoute) -> set[tuple[int, int, int, int]]:
    return {
        (
            int(waypoint.road_id),
            int(waypoint.section_id),
            int(waypoint.lane_id),
            int(round(float(waypoint.s) / 10.0)),
        )
        for waypoint in route.waypoints
    }


def candidate_rank(
    candidate: Candidate,
    selected: list[Candidate],
) -> tuple[float, float, float, int]:
    if selected:
        min_start_distance = min(
            candidate.route.spawn_transform.location.distance(item.route.spawn_transform.location)
            for item in selected
        )
        candidate_bins = route_bins(candidate.route)
        maximum_overlap = max(
            len(candidate_bins & route_bins(item.route)) / max(1, len(candidate_bins))
            for item in selected
        )
    else:
        min_start_distance = 1_000.0
        maximum_overlap = 0.0
    event_center_score = sum(
        abs(float(event["progress_fraction"]) - 0.5) for event in candidate.turn_events
    )
    return (
        maximum_overlap,
        -min(min_start_distance, 200.0),
        event_center_score,
        candidate.route.spawn_index,
    )


def select_candidates(
    map_: carla.Map,
    spawn_points: list[carla.Transform],
    dense_step_m: float,
    selection_seed: int,
    variants_per_spawn: int,
    straight_spacing_m: float,
    turn_context_m: float,
) -> tuple[list[Candidate], dict[str, object]]:
    specifications = [
        ("straight", "Straight control", 111),
        ("left", "Single left turn", 126),
        ("right", "Single right turn", 126),
        ("zigzag", "Left-right zigzag", 156),
        ("complex", "Multi-turn mixed route", 181),
    ]
    max_points = max(item[2] for item in specifications)
    indexed_spawns = sorted(
        enumerate(spawn_points),
        key=lambda item: tuple(canonical_transform(item[1])[field] for field in ("x", "y", "z", "yaw")),
    )
    pools: dict[str, list[Candidate]] = {kind: [] for kind, _, _ in specifications}
    signatures: set[tuple[tuple[int, int, int, float], ...]] = set()
    attempted = 0
    complete = 0

    for ordered_index, (spawn_index, spawn_transform) in enumerate(indexed_spawns):
        for variant in range(variants_per_spawn):
            attempted += 1
            branch_seed = selection_seed + ordered_index * 1009 + variant * 1_000_003
            full_route = make_connected_route(
                map_, spawn_index, spawn_transform, dense_step_m, max_points, branch_seed
            )
            if full_route is None:
                continue
            complete += 1
            for kind, label, point_count in specifications:
                route = route_prefix(full_route, point_count)
                signature = tuple(
                    (
                        int(waypoint.road_id),
                        int(waypoint.section_id),
                        int(waypoint.lane_id),
                        round(float(waypoint.s), 2),
                    )
                    for waypoint in route.waypoints
                )
                signature_key = (kind, signature)
                if signature_key in signatures:
                    continue
                events = detect_turn_events(route.waypoints)
                if not category_matches(kind, events):
                    continue
                signatures.add(signature_key)
                length_m, _ = route_length_m(route.waypoints)
                pools[kind].append(
                    Candidate(
                        kind=kind,
                        label=label,
                        route=route,
                        turn_events=events,
                        adaptive_indices=adaptive_indices(
                            route.waypoints,
                            events,
                            dense_step_m,
                            straight_spacing_m,
                            turn_context_m,
                        ),
                        dense_length_m=length_m,
                    )
                )

    selected: list[Candidate] = []
    for kind, _, _ in specifications:
        pool = pools[kind]
        if not pool:
            raise RuntimeError(f"no route candidate matched category {kind!r}")
        pool.sort(key=lambda candidate: candidate_rank(candidate, selected))
        chosen = pool[0]
        chosen.route.route_id = f"candidate_{len(selected) + 1:02d}_{kind}"
        selected.append(chosen)

    spawn_catalogue = [canonical_transform(transform) for _, transform in indexed_spawns]
    return selected, {
        "method": "enumerate seeded direct Waypoint.next(2 m) paths, classify heading-change events, then diversify overlap and starts",
        "selection_seed": selection_seed,
        "variants_per_spawn": variants_per_spawn,
        "attempted_dense_paths": attempted,
        "complete_dense_paths": complete,
        "matching_pool_sizes": {kind: len(pool) for kind, pool in pools.items()},
        "native_spawn_point_count": len(spawn_points),
        "sorted_spawn_catalogue_sha256": hashlib.sha256(
            json.dumps(spawn_catalogue, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def validate_candidate(candidate: Candidate, dense_step_m: float) -> dict[str, object]:
    dense_connected = []
    for current, successor in zip(candidate.route.waypoints, candidate.route.waypoints[1:]):
        dense_connected.append(
            any(
                int(item.id) == int(successor.id)
                and item.transform.location.distance(successor.transform.location) < 0.05
                for item in current.next(dense_step_m)
            )
        )
    adaptive = [candidate.route.waypoints[index] for index in candidate.adaptive_indices]
    _, adaptive_gaps = route_length_m(adaptive)
    return {
        "status": "passed" if all(dense_connected) and len(adaptive) >= 10 else "failed",
        "dense_waypoint_count": len(candidate.route.waypoints),
        "dense_connected_edges": sum(dense_connected),
        "dense_expected_edges": len(candidate.route.waypoints) - 1,
        "all_dense_edges_connected": all(dense_connected),
        "adaptive_waypoint_count": len(adaptive),
        "adaptive_has_at_least_ten_waypoints": len(adaptive) >= 10,
        "adaptive_maximum_gap_m": max(adaptive_gaps, default=0.0),
        "length_m": candidate.dense_length_m,
    }


def draw_candidate(
    world: carla.World,
    candidate: Candidate,
    color: carla.Color,
    lifetime_seconds: float,
    draw_markers: bool,
) -> dict[str, object]:
    debug = world.debug
    dense_locations = [
        waypoint.transform.location + carla.Location(z=0.65)
        for waypoint in candidate.route.waypoints
    ]
    for first, second in zip(dense_locations, dense_locations[1:]):
        debug.draw_line(first, second, 0.65, color, lifetime_seconds, False)
    marker_count = 0
    if draw_markers:
        for index in candidate.adaptive_indices:
            location = dense_locations[index] + carla.Location(z=0.05)
            radius = 0.75 if index not in (0, len(candidate.route.waypoints) - 1) else 1.35
            debug.draw_line(
                location + carla.Location(x=-radius),
                location + carla.Location(x=radius),
                0.18,
                color,
                lifetime_seconds,
                False,
            )
            debug.draw_line(
                location + carla.Location(y=-radius),
                location + carla.Location(y=radius),
                0.18,
                color,
                lifetime_seconds,
                False,
            )
            marker_count += 1
    return {
        "dense_line_segments": len(dense_locations) - 1,
        "adaptive_cross_markers": marker_count,
        "point_primitives": 0,
        "rendering": "draw_line only; crosses mark proposed adaptive waypoints",
    }


def candidate_document(
    candidate: Candidate,
    map_name: str,
    dense_step_m: float,
    straight_spacing_m: float,
    turn_context_m: float,
    validation: dict[str, object],
) -> dict[str, object]:
    adaptive = [candidate.route.waypoints[index] for index in candidate.adaptive_indices]
    return {
        "schema_version": 1,
        "status": "visual_candidate_only_not_adopted",
        "candidate_id": candidate.route.route_id,
        "candidate_kind": candidate.kind,
        "candidate_label": candidate.label,
        "map_name": map_name,
        "dense_reference": {
            "step_m": dense_step_m,
            "waypoint_count": len(candidate.route.waypoints),
            "waypoints": [
                waypoint_to_dict(waypoint, order)
                for order, waypoint in enumerate(candidate.route.waypoints)
            ],
        },
        "adaptive_proposal": {
            "straight_spacing_m": straight_spacing_m,
            "dense_spacing_m_near_turns": dense_step_m,
            "turn_context_m": turn_context_m,
            "dense_indices": candidate.adaptive_indices,
            "waypoint_count": len(adaptive),
            "waypoints": [waypoint_to_dict(waypoint, order) for order, waypoint in enumerate(adaptive)],
        },
        "turn_events": candidate.turn_events,
        "spawn_point_index_in_carla_map": candidate.route.spawn_index,
        "spawn_transform": transform_to_dict(candidate.route.spawn_transform),
        "branch_seed": candidate.route.branch_seed,
        "length_m": candidate.dense_length_m,
        "start": location_to_dict(candidate.route.waypoints[0].transform.location),
        "finish": location_to_dict(candidate.route.waypoints[-1].transform.location),
        "validation": validation,
        "autopilot_status": "not_run_for_visual_candidates",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--map-name", default="Town01_Opt")
    parser.add_argument("--dense-step-m", type=float, default=2.0)
    parser.add_argument("--straight-spacing-m", type=float, default=10.0)
    parser.add_argument("--turn-context-m", type=float, default=12.0)
    parser.add_argument("--selection-seed", type=int, default=20260919)
    parser.add_argument("--variants-per-spawn", type=int, default=4)
    parser.add_argument("--debug-lifetime-seconds", type=float, default=20.0)
    parser.add_argument("--overview-width", type=int, default=1024)
    parser.add_argument("--overview-height", type=int, default=1024)
    parser.add_argument("--overview-fov", type=float, default=90.0)
    args = parser.parse_args()

    if args.dense_step_m <= 0.0 or args.straight_spacing_m <= 0.0:
        raise SystemExit("waypoint spacings must be positive")
    if args.straight_spacing_m < args.dense_step_m:
        raise SystemExit("straight spacing must be at least the dense spacing")
    run_dir = args.run_dir.resolve()
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.is_file():
        raise SystemExit(f"run directory was not created by create_run.py: {run_dir}")

    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout)
    world: carla.World | None = None
    original_settings: dict[str, object] | None = None
    try:
        available_maps = list(client.get_available_maps())
        resolved_map = next(
            (name for name in available_maps if short_map_name(name).lower() == args.map_name.lower()),
            None,
        )
        if resolved_map is None:
            raise RuntimeError(f"{args.map_name} is not available")
        world = client.load_world(resolved_map, reset_settings=False, map_layers=carla.MapLayer.All)
        original_settings = configure_synchronous_world(world)
        map_ = world.get_map()
        if short_map_name(map_.name).lower() != "town01_opt":
            raise RuntimeError(f"loaded {map_.name!r}, expected Town01_Opt")
        road_line_operation = hide_road_lines(world)
        all_waypoints = sorted(map_.generate_waypoints(args.dense_step_m), key=waypoint_sort_key)
        spawn_points = list(map_.get_spawn_points())
        candidates, selection = select_candidates(
            map_,
            spawn_points,
            args.dense_step_m,
            args.selection_seed,
            args.variants_per_spawn,
            args.straight_spacing_m,
            args.turn_context_m,
        )
        validations = {
            candidate.route.route_id: validate_candidate(candidate, args.dense_step_m)
            for candidate in candidates
        }
        if not all(item["status"] == "passed" for item in validations.values()):
            raise RuntimeError(f"candidate validation failed: {validations}")

        documents: dict[str, dict[str, object]] = {}
        for candidate in candidates:
            candidate_id = candidate.route.route_id
            document = candidate_document(
                candidate,
                map_.name,
                args.dense_step_m,
                args.straight_spacing_m,
                args.turn_context_m,
                validations[candidate_id],
            )
            documents[candidate_id] = document
            write_json(run_dir / "candidates" / f"{candidate_id}.json", document)

        overview_drawings: dict[str, dict[str, object]] = {}
        for number, candidate in enumerate(candidates):
            overview_drawings[candidate.route.route_id] = draw_candidate(
                world,
                candidate,
                ROUTE_COLORS[number],
                args.debug_lifetime_seconds,
                draw_markers=False,
            )
        overview_path = run_dir / "previews" / "candidate_routes_overview.png"
        overview = capture_topdown_overview(
            world,
            all_waypoints,
            overview_path,
            args.overview_width,
            args.overview_height,
            args.overview_fov,
            args.timeout,
        )
        overview["path"] = overview_path.relative_to(run_dir).as_posix()
        world.debug.clear_debug_shape()
        world.debug.clear_debug_string()

        per_candidate: dict[str, dict[str, object]] = {}
        for number, candidate in enumerate(candidates):
            drawing = draw_candidate(
                world,
                candidate,
                ROUTE_COLORS[number],
                args.debug_lifetime_seconds,
                draw_markers=True,
            )
            candidate_id = candidate.route.route_id
            image_path = run_dir / "previews" / "candidates" / f"{candidate_id}.png"
            capture = capture_topdown_overview(
                world,
                candidate.route.waypoints,
                image_path,
                args.overview_width,
                args.overview_height,
                args.overview_fov,
                args.timeout,
            )
            capture["path"] = image_path.relative_to(run_dir).as_posix()
            per_candidate[candidate_id] = {"drawing": drawing, "overview": capture}
            world.debug.clear_debug_shape()
            world.debug.clear_debug_string()

        index = {
            "schema_version": 1,
            "status": "visual_candidates_only_not_adopted",
            "map_name": map_.name,
            "dense_step_m": args.dense_step_m,
            "adaptive_policy": {
                "straight_spacing_m": args.straight_spacing_m,
                "turn_spacing_m": args.dense_step_m,
                "turn_context_m": args.turn_context_m,
            },
            "selection": selection,
            "candidate_count": len(candidates),
            "overview": overview["path"],
            "candidates": [
                {
                    "candidate_id": candidate.route.route_id,
                    "kind": candidate.kind,
                    "label": candidate.label,
                    "path": f"candidates/{candidate.route.route_id}.json",
                    "preview": per_candidate[candidate.route.route_id]["overview"]["path"],
                    "length_m": candidate.dense_length_m,
                    "dense_waypoint_count": len(candidate.route.waypoints),
                    "adaptive_waypoint_count": len(candidate.adaptive_indices),
                    "turn_events": candidate.turn_events,
                    "start": location_to_dict(candidate.route.waypoints[0].transform.location),
                    "finish": location_to_dict(candidate.route.waypoints[-1].transform.location),
                }
                for candidate in candidates
            ],
        }
        write_json(run_dir / "candidate_routes.json", index)
        write_json(
            run_dir / "debug_visualization.json",
            {
                "rendering": "DebugHelper draw_line only; no draw_point primitives",
                "overview": overview,
                "overview_drawings": overview_drawings,
                "per_candidate": per_candidate,
                "cleanup": "All debug shapes and strings explicitly cleared after each capture.",
            },
        )
        validation = {
            "status": "passed",
            "checks": {
                "actual_map_is_town01_opt": short_map_name(map_.name).lower() == "town01_opt",
                "road_lines_were_hidden": road_line_operation["applied"] is True,
                "exactly_five_visual_candidates": len(candidates) == 5,
                "all_dense_reference_edges_connected": all(
                    item["all_dense_edges_connected"] for item in validations.values()
                ),
                "all_adaptive_paths_have_at_least_ten_waypoints": all(
                    item["adaptive_has_at_least_ten_waypoints"] for item in validations.values()
                ),
                "overview_is_png": overview_path.read_bytes()[:8] == PNG_SIGNATURE,
                "all_candidate_previews_are_png": all(
                    (run_dir / item["overview"]["path"]).read_bytes()[:8] == PNG_SIGNATURE
                    for item in per_candidate.values()
                ),
                "debug_point_primitives_are_absent": all(
                    item["drawing"]["point_primitives"] == 0 for item in per_candidate.values()
                ),
            },
            "candidate_validations": validations,
            "scope": "Visual proposal only; candidates are not adopted and no vehicle/TM drive was run.",
        }
        write_json(run_dir / "validation.json", validation)
        update_metadata(
            metadata_path,
            state="running",
            carla_client_version=client.get_client_version(),
            carla_server_version=client.get_server_version(),
            map_name=map_.name,
            road_line_operation=road_line_operation,
            candidate_route_probe={
                "status": "visual_candidates_only_not_adopted",
                "candidate_index_path": "candidate_routes.json",
                "debug_visualization_path": "debug_visualization.json",
                "selection_seed": args.selection_seed,
                "dense_step_m": args.dense_step_m,
                "straight_spacing_m": args.straight_spacing_m,
                "turn_context_m": args.turn_context_m,
            },
            validation_path="validation.json",
            validation_status="passed",
        )
        print(run_dir / "candidate_routes.json")
    except Exception as exc:
        update_metadata(metadata_path, state="failed", stage2_candidate_routes_error=str(exc))
        raise
    finally:
        if world is not None:
            world.debug.clear_debug_shape()
            world.debug.clear_debug_string()
        if world is not None and original_settings is not None:
            restore_world_settings(world, original_settings)


if __name__ == "__main__":
    main()
