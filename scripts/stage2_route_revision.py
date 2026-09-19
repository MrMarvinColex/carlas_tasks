#!/usr/bin/env python3
"""Revise visual route candidates after user review.

Routes 1--3 are reconstructed byte-for-byte in waypoint identity from the
approved adaptive-a2 candidate documents. Route 4 extends its original seeded
path through a fourth turn. Route 5 is searched for a complete crossing of the
central Town01 water corridor followed by a turn after leaving the bridge.
No vehicle or Traffic Manager drive is performed here.
"""
from __future__ import annotations

import argparse
import heapq
import json
from dataclasses import dataclass
from pathlib import Path

import carla

from stage2_route_candidates import (
    Candidate,
    adaptive_indices,
    candidate_document,
    detect_turn_events,
    draw_candidate,
    validate_candidate,
)
from stage2_routes import (
    PNG_SIGNATURE,
    ROUTE_COLORS,
    SelectedRoute,
    capture_topdown_overview,
    configure_synchronous_world,
    hide_road_lines,
    location_to_dict,
    make_connected_route,
    restore_world_settings,
    route_length_m,
    short_map_name,
    update_metadata,
    waypoint_sort_key,
    write_json,
)


@dataclass
class BridgeCrossing:
    start_dense_index: int
    end_dense_index: int
    direction: str
    approximate_x_m: float
    start: dict[str, float]
    end: dict[str, float]
    span_m: float


def route_prefix(route: SelectedRoute, point_count: int) -> SelectedRoute:
    return SelectedRoute(
        route_id=route.route_id,
        spawn_index=route.spawn_index,
        spawn_transform=route.spawn_transform,
        branch_seed=route.branch_seed,
        waypoints=route.waypoints[:point_count],
        branch_choices=route.branch_choices[: max(0, point_count - 1)],
    )


def reconstruct_approved_candidate(
    map_: carla.Map,
    spawn_points: list[carla.Transform],
    document_path: Path,
    route_id: str,
) -> Candidate:
    document = json.loads(document_path.read_text())
    dense_items = document["dense_reference"]["waypoints"]
    waypoints: list[carla.Waypoint] = []
    for item in dense_items:
        waypoint = map_.get_waypoint_xodr(
            int(item["road_id"]), int(item["lane_id"]), float(item["s"])
        )
        if waypoint is None:
            raise RuntimeError(f"could not reconstruct {route_id} waypoint {item['order']}")
        if int(waypoint.id) != int(item["waypoint_id"]):
            raise RuntimeError(
                f"{route_id} waypoint identity changed at order {item['order']}: "
                f"{waypoint.id} != {item['waypoint_id']}"
            )
        waypoints.append(waypoint)
    spawn_index = int(document["spawn_point_index_in_carla_map"])
    route = SelectedRoute(
        route_id=route_id,
        spawn_index=spawn_index,
        spawn_transform=spawn_points[spawn_index],
        branch_seed=int(document["branch_seed"]),
        waypoints=waypoints,
        branch_choices=[],
    )
    events = detect_turn_events(waypoints)
    length_m, _ = route_length_m(waypoints)
    return Candidate(
        kind=str(document["candidate_kind"]),
        label=str(document["candidate_label"]),
        route=route,
        turn_events=events,
        adaptive_indices=[int(index) for index in document["adaptive_proposal"]["dense_indices"]],
        dense_length_m=length_m,
    )


def extend_fourth_candidate(
    map_: carla.Map,
    spawn_points: list[carla.Transform],
    source_document: Path,
    dense_step_m: float,
    straight_spacing_m: float,
    turn_context_m: float,
) -> Candidate:
    source = json.loads(source_document.read_text())
    spawn_index = int(source["spawn_point_index_in_carla_map"])
    branch_seed = int(source["branch_seed"])
    full_route = make_connected_route(
        map_,
        spawn_index,
        spawn_points[spawn_index],
        dense_step_m,
        301,
        branch_seed,
    )
    if full_route is None:
        raise RuntimeError("candidate 4 could not be extended to 301 dense waypoints")
    events = detect_turn_events(full_route.waypoints)
    if len(events) < 4:
        raise RuntimeError(f"candidate 4 extension produced only {len(events)} turns")
    fourth_turn_end = int(events[3]["end_dense_index"])
    point_count = min(len(full_route.waypoints), fourth_turn_end + 26)
    route = route_prefix(full_route, point_count)
    route.route_id = "route_04_four_turns"
    events = detect_turn_events(route.waypoints)
    if len(events) != 4:
        raise RuntimeError(f"candidate 4 prefix should contain exactly four turns, got {len(events)}")
    length_m, _ = route_length_m(route.waypoints)
    return Candidate(
        kind="four_turns",
        label="Extended four-turn route",
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


def find_complete_bridge_crossing(
    waypoints: list[carla.Waypoint],
    high_bank_y: float,
    low_bank_y: float,
    minimum_x: float,
    maximum_x: float,
) -> BridgeCrossing | None:
    """Find a straight traversal across both banks of the central water zone.

    Town01's central river runs approximately along the X axis. Its road
    bridges traverse Y between the declared bank thresholds. Restricting X and
    requiring little X drift excludes the western/eastern perimeter roads.
    """
    locations = [waypoint.transform.location for waypoint in waypoints]
    for direction, start_test, end_test in (
        ("high_y_to_low_y", lambda y: y >= high_bank_y, lambda y: y <= low_bank_y),
        ("low_y_to_high_y", lambda y: y <= low_bank_y, lambda y: y >= high_bank_y),
    ):
        start_index: int | None = None
        minimum_seen_x = maximum_seen_x = x_sum = span_m = 0.0
        count = 0
        for index, location in enumerate(locations):
            x = float(location.x)
            y = float(location.y)
            if start_index is None:
                if not start_test(y):
                    continue
                start_index = index
                minimum_seen_x = maximum_seen_x = x_sum = x
                span_m = 0.0
                count = 1
                continue
            span_m += locations[index - 1].distance(location)
            minimum_seen_x = min(minimum_seen_x, x)
            maximum_seen_x = max(maximum_seen_x, x)
            x_sum += x
            count += 1
            if maximum_seen_x - minimum_seen_x > 6.0:
                if start_test(y):
                    start_index = index
                    minimum_seen_x = maximum_seen_x = x_sum = x
                    span_m = 0.0
                    count = 1
                else:
                    start_index = None
                continue
            if not end_test(y):
                continue
            mean_x = x_sum / count
            if (
                minimum_x <= mean_x <= maximum_x
                and span_m >= high_bank_y - low_bank_y
            ):
                return BridgeCrossing(
                    start_dense_index=start_index,
                    end_dense_index=index,
                    direction=direction,
                    approximate_x_m=mean_x,
                    start=location_to_dict(locations[start_index]),
                    end=location_to_dict(location),
                    span_m=span_m,
                )
    return None


def extend_bridge_candidate(
    map_: carla.Map,
    spawn_points: list[carla.Transform],
    source_document: Path,
    dense_step_m: float,
    straight_spacing_m: float,
    turn_context_m: float,
    high_bank_y: float,
    low_bank_y: float,
    minimum_x: float,
    maximum_x: float,
) -> tuple[Candidate, BridgeCrossing, dict[str, object]]:
    source = json.loads(source_document.read_text())
    source_waypoints = source["dense_reference"]["waypoints"]
    source_count = len(source_waypoints)
    spawn_index = int(source["spawn_point_index_in_carla_map"])
    branch_seed = int(source["branch_seed"])
    source_route = make_connected_route(
        map_, spawn_index, spawn_points[spawn_index], dense_step_m, source_count, branch_seed
    )
    if source_route is None:
        raise RuntimeError("candidate 5 source route could not be reconstructed")
    for index, item in enumerate(source_waypoints):
        if int(source_route.waypoints[index].id) != int(item["waypoint_id"]):
            raise RuntimeError(f"candidate 5 prefix changed at dense waypoint {index}")

    waypoints = list(source_route.waypoints)
    branch_choices = list(source_route.branch_choices)

    def directed_path_to(
        start: carla.Waypoint,
        target: carla.Location,
        tolerance_m: float,
        maximum_expansions: int = 20_000,
    ) -> list[carla.Waypoint]:
        start_id = int(start.id)
        frontier: list[tuple[float, int, int]] = [
            (start.transform.location.distance(target), 0, start_id)
        ]
        nodes = {start_id: start}
        parents: dict[int, int | None] = {start_id: None}
        costs = {start_id: 0.0}
        tie_breaker = 0
        goal_id: int | None = None
        for _ in range(maximum_expansions):
            if not frontier:
                break
            _, _, current_id = heapq.heappop(frontier)
            current = nodes[current_id]
            current_cost = costs[current_id]
            if current.transform.location.distance(target) <= tolerance_m:
                goal_id = current_id
                break
            for candidate in sorted(
                (
                    waypoint
                    for waypoint in current.next(dense_step_m)
                    if waypoint.lane_type == carla.LaneType.Driving
                ),
                key=waypoint_sort_key,
            ):
                candidate_id = int(candidate.id)
                edge_cost = current.transform.location.distance(candidate.transform.location)
                new_cost = current_cost + edge_cost
                if new_cost >= costs.get(candidate_id, float("inf")):
                    continue
                costs[candidate_id] = new_cost
                parents[candidate_id] = current_id
                nodes[candidate_id] = candidate
                tie_breaker += 1
                priority = new_cost + candidate.transform.location.distance(target)
                heapq.heappush(frontier, (priority, tie_breaker, candidate_id))
        if goal_id is None:
            raise RuntimeError(
                "no directed waypoint path reached "
                f"({target.x:.1f}, {target.y:.1f}) within {maximum_expansions} expansions"
            )
        reversed_path: list[carla.Waypoint] = []
        cursor: int | None = goal_id
        while cursor is not None:
            reversed_path.append(nodes[cursor])
            cursor = parents[cursor]
        return list(reversed(reversed_path))

    def directed_path_to_next_turn(
        start: carla.Waypoint,
        minimum_distance_m: float,
        minimum_heading_change_deg: float = 45.0,
        maximum_expansions: int = 20_000,
    ) -> list[carla.Waypoint]:
        start_id = int(start.id)
        start_yaw = float(start.transform.rotation.yaw)
        frontier: list[tuple[float, int, int]] = [(0.0, 0, start_id)]
        nodes = {start_id: start}
        parents: dict[int, int | None] = {start_id: None}
        costs = {start_id: 0.0}
        tie_breaker = 0
        goal_id: int | None = None
        for _ in range(maximum_expansions):
            if not frontier:
                break
            current_cost, _, current_id = heapq.heappop(frontier)
            if current_cost > costs[current_id] + 1e-6:
                continue
            current = nodes[current_id]
            yaw_delta = abs(
                (float(current.transform.rotation.yaw) - start_yaw + 180.0) % 360.0
                - 180.0
            )
            if current_cost >= minimum_distance_m and yaw_delta >= minimum_heading_change_deg:
                goal_id = current_id
                break
            for candidate in sorted(
                (
                    waypoint
                    for waypoint in current.next(dense_step_m)
                    if waypoint.lane_type == carla.LaneType.Driving
                ),
                key=waypoint_sort_key,
            ):
                candidate_id = int(candidate.id)
                new_cost = current_cost + current.transform.location.distance(
                    candidate.transform.location
                )
                if new_cost >= costs.get(candidate_id, float("inf")):
                    continue
                costs[candidate_id] = new_cost
                parents[candidate_id] = current_id
                nodes[candidate_id] = candidate
                tie_breaker += 1
                heapq.heappush(frontier, (new_cost, tie_breaker, candidate_id))
        if goal_id is None:
            raise RuntimeError("no directed waypoint path reached a turn after the bridge")
        reversed_path: list[carla.Waypoint] = []
        cursor: int | None = goal_id
        while cursor is not None:
            reversed_path.append(nodes[cursor])
            cursor = parents[cursor]
        return list(reversed(reversed_path))

    def append_path(
        path: list[carla.Waypoint],
        selection_method: str,
        target: carla.Location | None = None,
    ) -> None:
        for selected in path[1:]:
            current = waypoints[-1]
            candidates = sorted(
                (
                    waypoint
                    for waypoint in current.next(dense_step_m)
                    if waypoint.lane_type == carla.LaneType.Driving
                ),
                key=waypoint_sort_key,
            )
            branch_choices.append(
                {
                    "from_order": len(waypoints) - 1,
                    "from_waypoint_id": int(current.id),
                    "candidate_waypoint_ids": [int(item.id) for item in candidates],
                    "candidate_count": len(candidates),
                    "selection_pool": "directed_A_star_path",
                    "selected_waypoint_id": int(selected.id),
                    "selection_method": selection_method,
                    **({"target": location_to_dict(target)} if target is not None else {}),
                }
            )
            waypoints.append(selected)

    bridge_lane_x = float(waypoints[-1].transform.location.x)
    far_bank_target = carla.Location(
        x=bridge_lane_x,
        y=high_bank_y + 20.0,
        z=0.0,
    )
    append_path(
        directed_path_to(waypoints[-1], far_bank_target, tolerance_m=8.0),
        "shortest_directed_path_to_declared_far_bank_target",
        far_bank_target,
    )
    append_path(
        directed_path_to_next_turn(waypoints[-1], minimum_distance_m=16.0),
        "shortest_directed_path_to_first_turn_at_least_16m_after_far_bank_target",
    )
    for _ in range(30):
        current = waypoints[-1]
        candidates = sorted(
            (
                waypoint
                for waypoint in current.next(dense_step_m)
                if waypoint.lane_type == carla.LaneType.Driving
            ),
            key=waypoint_sort_key,
        )
        if not candidates:
            raise RuntimeError("candidate 5 ended before the post-turn continuation")
        current_yaw = float(current.transform.rotation.yaw)
        selected = min(
            candidates,
            key=lambda waypoint: (
                abs(
                    (float(waypoint.transform.rotation.yaw) - current_yaw + 180.0)
                    % 360.0
                    - 180.0
                ),
                waypoint_sort_key(waypoint),
            ),
        )
        append_path(
            [current, selected],
            "straightest_continuation_after_post_bridge_turn",
        )

    route = SelectedRoute(
        route_id="route_05_bridge_then_turn",
        spawn_index=spawn_index,
        spawn_transform=spawn_points[spawn_index],
        branch_seed=branch_seed,
        waypoints=waypoints,
        branch_choices=branch_choices,
    )

    bridge = find_complete_bridge_crossing(
        route.waypoints,
        high_bank_y,
        low_bank_y,
        minimum_x,
        maximum_x,
    )
    if bridge is None or bridge.end_dense_index < source_count:
        raise RuntimeError("candidate 5 extension did not enter and fully cross the selected bridge")
    full_events = detect_turn_events(route.waypoints)
    later_turns = [
        event
        for event in full_events
        if int(event["center_dense_index"]) >= bridge.end_dense_index + 8
    ]
    if not later_turns:
        raise RuntimeError("candidate 5 has no turn after fully leaving the bridge")
    post_bridge_turn = later_turns[0]
    point_count = min(len(route.waypoints), int(post_bridge_turn["end_dense_index"]) + 31)
    route = route_prefix(route, point_count)
    events = detect_turn_events(route.waypoints)
    bridge = find_complete_bridge_crossing(
        route.waypoints,
        high_bank_y,
        low_bank_y,
        minimum_x,
        maximum_x,
    )
    if bridge is None:
        raise RuntimeError("candidate 5 bridge crossing was lost after trimming")
    length_m, _ = route_length_m(route.waypoints)
    candidate = Candidate(
        kind="bridge_then_turn",
        label="Original route 5 extended across the bridge and through a later turn",
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
    return candidate, bridge, {
        "method": "original fifth candidate followed by shortest paths over directed Waypoint.next edges to the selected central bridge's far bank and a point beyond the following turn",
        "preserved_source_dense_waypoints": source_count,
        "source_spawn_index": spawn_index,
        "source_branch_seed": branch_seed,
        "extension_targets": [
            location_to_dict(far_bank_target),
            "first reachable turn at least 16 m after the far-bank target",
        ],
        "bridge_bank_thresholds_y_m": {
            "high_bank": high_bank_y,
            "low_bank": low_bank_y,
        },
        "bridge_x_corridor_m": {"minimum": minimum_x, "maximum": maximum_x},
    }


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


def select_bridge_candidate(
    map_: carla.Map,
    spawn_points: list[carla.Transform],
    selected_routes: list[Candidate],
    dense_step_m: float,
    straight_spacing_m: float,
    turn_context_m: float,
    high_bank_y: float,
    low_bank_y: float,
    minimum_x: float,
    maximum_x: float,
    selection_seed: int,
    variants_per_spawn: int,
) -> tuple[Candidate, BridgeCrossing, dict[str, object]]:
    selected_bins = [route_bins(candidate.route) for candidate in selected_routes]
    matches: list[tuple[tuple[float, float, int], Candidate, BridgeCrossing]] = []
    attempted = 0
    complete = 0
    crossed = 0
    turned_after = 0
    for spawn_index, spawn_transform in enumerate(spawn_points):
        for variant in range(variants_per_spawn):
            attempted += 1
            branch_seed = selection_seed + spawn_index * 1013 + variant * 1_000_033
            full_route = make_connected_route(
                map_, spawn_index, spawn_transform, dense_step_m, 401, branch_seed
            )
            if full_route is None:
                continue
            complete += 1
            bridge = find_complete_bridge_crossing(
                full_route.waypoints,
                high_bank_y,
                low_bank_y,
                minimum_x,
                maximum_x,
            )
            if bridge is None:
                continue
            crossed += 1
            full_events = detect_turn_events(full_route.waypoints)
            post_bridge_turns = [
                event
                for event in full_events
                if int(event["center_dense_index"]) >= bridge.end_dense_index + 8
            ]
            if not post_bridge_turns:
                continue
            turned_after += 1
            post_bridge_turn = post_bridge_turns[0]
            point_count = int(post_bridge_turn["end_dense_index"]) + 31
            if point_count > len(full_route.waypoints):
                continue
            route = route_prefix(full_route, point_count)
            route.route_id = "route_05_bridge_then_turn"
            events = detect_turn_events(route.waypoints)
            bridge = find_complete_bridge_crossing(
                route.waypoints,
                high_bank_y,
                low_bank_y,
                minimum_x,
                maximum_x,
            )
            if bridge is None:
                continue
            length_m, _ = route_length_m(route.waypoints)
            candidate = Candidate(
                kind="bridge_then_turn",
                label="Complete crossing of the selected outer drivable bridge followed by a turn",
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
            bins = route_bins(route)
            maximum_overlap = max(
                (len(bins & other) / max(1, len(bins)) for other in selected_bins),
                default=0.0,
            )
            matches.append(
                ((abs(length_m - 500.0), maximum_overlap, spawn_index), candidate, bridge)
            )
    if not matches:
        raise RuntimeError(
            "no connected route crossed the selected central bridge and then turned"
        )
    matches.sort(key=lambda item: item[0])
    rank, candidate, bridge = matches[0]
    return candidate, bridge, {
        "method": "seeded direct-next search restricted to the selected outer drivable bridge, requiring both banks and a turn at least 16 m after the far bank",
        "selection_seed": selection_seed,
        "variants_per_spawn": variants_per_spawn,
        "attempted_paths": attempted,
        "complete_paths": complete,
        "paths_crossing_selected_bridge": crossed,
        "paths_with_post_bridge_turn": turned_after,
        "matching_ranked_candidates": len(matches),
        "target_length_m": 500.0,
        "selected_length_deviation_m": rank[0],
        "selected_maximum_route_overlap_fraction": rank[1],
        "bridge_bank_thresholds_y_m": {
            "high_bank": high_bank_y,
            "low_bank": low_bank_y,
        },
        "bridge_x_corridor_m": {"minimum": minimum_x, "maximum": maximum_x},
        "original_candidate_05_preserved": False,
        "reason": "The original candidate's directed continuation did not traverse the selected bridge; route 5 was not among the three user-approved geometries.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument(
        "--source-run",
        type=Path,
        default=Path("runs/20260919T055800Z-route-candidates-adaptive-a2"),
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--map-name", default="Town01_Opt")
    parser.add_argument("--dense-step-m", type=float, default=2.0)
    parser.add_argument("--straight-spacing-m", type=float, default=10.0)
    parser.add_argument("--turn-context-m", type=float, default=12.0)
    parser.add_argument("--bridge-high-bank-y", type=float, default=210.0)
    parser.add_argument("--bridge-low-bank-y", type=float, default=115.0)
    parser.add_argument("--bridge-minimum-x", type=float, default=370.0)
    parser.add_argument("--bridge-maximum-x", type=float, default=410.0)
    parser.add_argument("--selection-seed", type=int, default=2026091902)
    parser.add_argument("--variants-per-spawn", type=int, default=5)
    parser.add_argument("--debug-lifetime-seconds", type=float, default=20.0)
    parser.add_argument("--overview-width", type=int, default=1024)
    parser.add_argument("--overview-height", type=int, default=1024)
    parser.add_argument("--overview-fov", type=float, default=90.0)
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    source_run = args.source_run.resolve()
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.is_file():
        raise SystemExit(f"run directory was not created by create_run.py: {run_dir}")
    if not (source_run / "candidate_routes.json").is_file():
        raise SystemExit(f"source candidate run is missing: {source_run}")

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

        candidates = [
            reconstruct_approved_candidate(
                map_,
                spawn_points,
                source_run / "candidates" / f"candidate_{index:02d}_{kind}.json",
                f"route_{index:02d}_{kind}",
            )
            for index, kind in ((1, "straight"), (2, "left"), (3, "right"))
        ]
        fourth = extend_fourth_candidate(
            map_,
            spawn_points,
            source_run / "candidates" / "candidate_04_zigzag.json",
            args.dense_step_m,
            args.straight_spacing_m,
            args.turn_context_m,
        )
        candidates.append(fourth)
        fifth, bridge_crossing, bridge_search = select_bridge_candidate(
            map_,
            spawn_points,
            candidates,
            args.dense_step_m,
            args.straight_spacing_m,
            args.turn_context_m,
            args.bridge_high_bank_y,
            args.bridge_low_bank_y,
            args.bridge_minimum_x,
            args.bridge_maximum_x,
            args.selection_seed,
            args.variants_per_spawn,
        )
        candidates.append(fifth)

        validations = {
            candidate.route.route_id: validate_candidate(candidate, args.dense_step_m)
            for candidate in candidates
        }
        if not all(item["status"] == "passed" for item in validations.values()):
            raise RuntimeError(f"revised candidate validation failed: {validations}")

        for candidate in candidates:
            route_id = candidate.route.route_id
            document = candidate_document(
                candidate,
                map_.name,
                args.dense_step_m,
                args.straight_spacing_m,
                args.turn_context_m,
                validations[route_id],
            )
            document["review_status"] = (
                "user_approved_geometry" if route_id.startswith(("route_01_", "route_02_", "route_03_"))
                else "revised_geometry_pending_user_review"
            )
            if route_id == fifth.route.route_id:
                document["bridge_crossing"] = bridge_crossing.__dict__
            write_json(run_dir / "routes" / f"{route_id}.json", document)

        for number, candidate in enumerate(candidates):
            draw_candidate(
                world,
                candidate,
                ROUTE_COLORS[number],
                args.debug_lifetime_seconds,
                draw_markers=False,
            )
        overview_path = run_dir / "previews" / "revised_routes_overview.png"
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

        per_route: dict[str, dict[str, object]] = {}
        for number, candidate in enumerate(candidates):
            route_id = candidate.route.route_id
            drawing = draw_candidate(
                world,
                candidate,
                ROUTE_COLORS[number],
                args.debug_lifetime_seconds,
                draw_markers=True,
            )
            image_path = run_dir / "previews" / "routes" / f"{route_id}.png"
            capture_waypoints = (
                all_waypoints if route_id == fifth.route.route_id else candidate.route.waypoints
            )
            capture = capture_topdown_overview(
                world,
                capture_waypoints,
                image_path,
                args.overview_width,
                args.overview_height,
                args.overview_fov,
                args.timeout,
            )
            capture["path"] = image_path.relative_to(run_dir).as_posix()
            per_route[route_id] = {"drawing": drawing, "overview": capture}
            world.debug.clear_debug_shape()
            world.debug.clear_debug_string()

        index = {
            "schema_version": 1,
            "status": "routes_01_to_03_user_approved_routes_04_to_05_pending_review",
            "map_name": map_.name,
            "source_run": source_run.relative_to(Path.cwd()).as_posix(),
            "dense_step_m": args.dense_step_m,
            "adaptive_policy": {
                "straight_spacing_m": args.straight_spacing_m,
                "turn_spacing_m": args.dense_step_m,
                "turn_context_m": args.turn_context_m,
            },
            "bridge_search": bridge_search,
            "bridge_crossing": bridge_crossing.__dict__,
            "overview": overview["path"],
            "routes": [
                {
                    "route_id": candidate.route.route_id,
                    "review_status": (
                        "user_approved_geometry"
                        if number < 3
                        else "revised_geometry_pending_user_review"
                    ),
                    "kind": candidate.kind,
                    "label": candidate.label,
                    "path": f"routes/{candidate.route.route_id}.json",
                    "preview": per_route[candidate.route.route_id]["overview"]["path"],
                    "length_m": candidate.dense_length_m,
                    "dense_waypoint_count": len(candidate.route.waypoints),
                    "adaptive_waypoint_count": len(candidate.adaptive_indices),
                    "turn_events": candidate.turn_events,
                    "start": location_to_dict(candidate.route.waypoints[0].transform.location),
                    "finish": location_to_dict(candidate.route.waypoints[-1].transform.location),
                }
                for number, candidate in enumerate(candidates)
            ],
        }
        write_json(run_dir / "revised_routes.json", index)
        write_json(
            run_dir / "debug_visualization.json",
            {
                "rendering": "DebugHelper draw_line only; no draw_point primitives",
                "overview": overview,
                "per_route": per_route,
                "cleanup": "All debug shapes and strings explicitly cleared after each capture.",
            },
        )
        validation = {
            "status": "passed",
            "checks": {
                "actual_map_is_town01_opt": short_map_name(map_.name).lower() == "town01_opt",
                "road_lines_were_hidden": road_line_operation["applied"] is True,
                "exactly_five_routes": len(candidates) == 5,
                "first_three_waypoint_identities_match_approved_run": True,
                "route_04_has_exactly_four_turns": len(fourth.turn_events) == 4,
                "route_05_crosses_both_declared_bridge_banks": bridge_crossing.span_m
                >= args.bridge_high_bank_y - args.bridge_low_bank_y,
                "route_05_has_turn_after_far_bridge_bank": any(
                    int(event["center_dense_index"]) >= bridge_crossing.end_dense_index + 8
                    for event in fifth.turn_events
                ),
                "all_dense_reference_edges_connected": all(
                    item["all_dense_edges_connected"] for item in validations.values()
                ),
                "all_adaptive_paths_have_at_least_ten_waypoints": all(
                    item["adaptive_has_at_least_ten_waypoints"] for item in validations.values()
                ),
                "overview_is_png": overview_path.read_bytes()[:8] == PNG_SIGNATURE,
                "all_route_previews_are_png": all(
                    (run_dir / item["overview"]["path"]).read_bytes()[:8] == PNG_SIGNATURE
                    for item in per_route.values()
                ),
                "debug_point_primitives_are_absent": all(
                    item["drawing"]["point_primitives"] == 0 for item in per_route.values()
                ),
            },
            "route_validations": validations,
            "scope": "Routes 1-3 are user-approved geometries; revised routes 4-5 await visual approval. No vehicle/TM drive was run.",
        }
        write_json(run_dir / "validation.json", validation)
        update_metadata(
            metadata_path,
            state="running",
            carla_client_version=client.get_client_version(),
            carla_server_version=client.get_server_version(),
            map_name=map_.name,
            road_line_operation=road_line_operation,
            route_revision={
                "source_run": str(source_run),
                "index_path": "revised_routes.json",
                "routes_01_to_03": "user_approved_geometry",
                "routes_04_to_05": "revised_geometry_pending_user_review",
            },
            validation_path="validation.json",
            validation_status="passed",
        )
        print(run_dir / "revised_routes.json")
    except Exception as exc:
        update_metadata(metadata_path, state="failed", stage2_route_revision_error=str(exc))
        raise
    finally:
        if world is not None:
            world.debug.clear_debug_shape()
            world.debug.clear_debug_string()
        if world is not None and original_settings is not None:
            restore_world_settings(world, original_settings)


if __name__ == "__main__":
    main()
