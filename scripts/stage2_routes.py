#!/usr/bin/env python3
"""Construct and visually inspect five connected Town01_Opt routes.

This is the route-selection half of Stage 2.  It deliberately does *not* spawn
an ego vehicle or enable Traffic Manager: those are separate acceptance checks
for the driving half of the stage.  Each selected edge is obtained directly
from ``Waypoint.next(resolution)`` and is rechecked before it is written.

The script assumes its run directory was created by ``scripts/create_run.py``.
It writes a complete finite waypoint sample, one JSON file per route, a route
index, and a top-down RGB overview with temporary CARLA DebugHelper drawings.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import queue
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import carla


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ROUTE_COLORS = (
    carla.Color(231, 76, 60),
    carla.Color(52, 152, 219),
    carla.Color(46, 204, 113),
    carla.Color(241, 196, 15),
    carla.Color(155, 89, 182),
)


@dataclass
class SelectedRoute:
    """A route whose waypoint objects remain available for API revalidation."""

    route_id: str
    spawn_index: int
    spawn_transform: carla.Transform
    branch_seed: int
    waypoints: list[carla.Waypoint]
    branch_choices: list[dict[str, Any]]


def update_metadata(path: Path, **values: object) -> None:
    metadata = json.loads(path.read_text())
    metadata.update(values)
    path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def short_map_name(map_name: str) -> str:
    return map_name.rstrip("/").rsplit("/", 1)[-1]


def transform_to_dict(transform: carla.Transform) -> dict[str, dict[str, float]]:
    return {
        "location": {
            "x": float(transform.location.x),
            "y": float(transform.location.y),
            "z": float(transform.location.z),
        },
        "rotation": {
            "roll": float(transform.rotation.roll),
            "pitch": float(transform.rotation.pitch),
            "yaw": float(transform.rotation.yaw),
        },
    }


def location_to_dict(location: carla.Location) -> dict[str, float]:
    return {"x": float(location.x), "y": float(location.y), "z": float(location.z)}


def waypoint_sort_key(waypoint: carla.Waypoint) -> tuple[int, int, int, float, float, float, float]:
    location = waypoint.transform.location
    return (
        int(waypoint.road_id),
        int(waypoint.section_id),
        int(waypoint.lane_id),
        round(float(waypoint.s), 5),
        round(float(location.x), 5),
        round(float(location.y), 5),
        round(float(location.z), 5),
    )


def waypoint_to_dict(waypoint: carla.Waypoint, ordinal: int | None = None) -> dict[str, object]:
    item: dict[str, object] = {
        "waypoint_id": int(waypoint.id),
        "transform": transform_to_dict(waypoint.transform),
        "road_id": int(waypoint.road_id),
        "section_id": int(waypoint.section_id),
        "lane_id": int(waypoint.lane_id),
        "s": float(waypoint.s),
        "lane_width_m": float(waypoint.lane_width),
        "lane_type": str(waypoint.lane_type),
        "is_junction": bool(waypoint.is_junction),
        "junction_id": int(waypoint.junction_id),
    }
    if ordinal is not None:
        item["order"] = ordinal
    return item


def canonical_transform(transform: carla.Transform) -> dict[str, float]:
    """Stable, compact spawn-point representation used in a provenance digest."""
    return {
        "x": round(float(transform.location.x), 5),
        "y": round(float(transform.location.y), 5),
        "z": round(float(transform.location.z), 5),
        "roll": round(float(transform.rotation.roll), 5),
        "pitch": round(float(transform.rotation.pitch), 5),
        "yaw": round(float(transform.rotation.yaw), 5),
    }


def distance_2d(first: carla.Location, second: carla.Location) -> float:
    return math.hypot(float(first.x - second.x), float(first.y - second.y))


def configure_synchronous_world(world: carla.World) -> dict[str, object]:
    settings = world.get_settings()
    original = {
        "synchronous_mode": bool(settings.synchronous_mode),
        "fixed_delta_seconds": settings.fixed_delta_seconds,
        "no_rendering_mode": bool(settings.no_rendering_mode),
    }
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 0.05
    settings.no_rendering_mode = False
    world.apply_settings(settings)
    world.tick()
    return original


def restore_world_settings(world: carla.World, original: dict[str, object]) -> None:
    settings = world.get_settings()
    settings.synchronous_mode = bool(original["synchronous_mode"])
    settings.fixed_delta_seconds = original["fixed_delta_seconds"]
    settings.no_rendering_mode = bool(original["no_rendering_mode"])
    world.apply_settings(settings)


def hide_road_lines(world: carla.World) -> dict[str, object]:
    label = getattr(carla.CityObjectLabel, "RoadLines", None)
    if label is None:
        raise RuntimeError("This CARLA client has no CityObjectLabel.RoadLines enum")
    objects = list(world.get_environment_objects(label))
    object_ids = sorted(int(environment_object.id) for environment_object in objects)
    if not object_ids:
        raise RuntimeError("Town01_Opt returned no RoadLines environment-object IDs")
    world.enable_environment_objects(set(object_ids), False)
    for _ in range(3):
        world.tick()
    return {
        "method": "World.enable_environment_objects(ids, False)",
        "target": "CityObjectLabel.RoadLines",
        "object_count": len(object_ids),
        "object_ids": object_ids,
        "ids_sha256": hashlib.sha256(",".join(map(str, object_ids)).encode()).hexdigest(),
        "applied": True,
        "stage1_evidence_run": "20260917T153000Z-town01-opt-coverage-b6e3",
        "scope": (
            "The operation is re-applied here. RGB/raw-semantic removal was verified "
            "at three declared locations in the cited Stage-1 run; this route probe "
            "adds a top-down RGB overview, not a new map-wide marking-coverage claim."
        ),
    }


def make_connected_route(
    map_: carla.Map,
    spawn_index: int,
    spawn_transform: carla.Transform,
    waypoint_step_m: float,
    point_count: int,
    branch_seed: int,
) -> SelectedRoute | None:
    """Follow direct ``Waypoint.next`` edges from one native spawn point."""
    current = map_.get_waypoint(
        spawn_transform.location,
        project_to_road=True,
        lane_type=carla.LaneType.Driving,
    )
    if current is None:
        return None
    waypoints = [current]
    branch_choices: list[dict[str, Any]] = []
    randomizer = random.Random(branch_seed)
    seen_keys = {waypoint_sort_key(current)}
    for step in range(1, point_count):
        candidates = sorted(
            (
                waypoint
                for waypoint in current.next(waypoint_step_m)
                if waypoint.lane_type == carla.LaneType.Driving
            ),
            key=waypoint_sort_key,
        )
        if not candidates:
            return None
        unseen = [candidate for candidate in candidates if waypoint_sort_key(candidate) not in seen_keys]
        available = unseen or candidates
        selected_index = randomizer.randrange(len(available))
        selected = available[selected_index]
        branch_choices.append(
            {
                "from_order": step - 1,
                "from_waypoint_id": int(current.id),
                "candidate_waypoint_ids": [int(candidate.id) for candidate in candidates],
                "candidate_count": len(candidates),
                "selection_pool": "unseen_candidates" if unseen else "all_candidates_after_loop_fallback",
                "selected_waypoint_id": int(selected.id),
                "selected_index_in_pool": selected_index,
            }
        )
        waypoints.append(selected)
        seen_keys.add(waypoint_sort_key(selected))
        current = selected
    return SelectedRoute(
        route_id="",
        spawn_index=spawn_index,
        spawn_transform=spawn_transform,
        branch_seed=branch_seed,
        waypoints=waypoints,
        branch_choices=branch_choices,
    )


def route_signature(route: SelectedRoute) -> tuple[tuple[int, int, int, float], ...]:
    return tuple(
        (int(waypoint.road_id), int(waypoint.section_id), int(waypoint.lane_id), round(float(waypoint.s), 3))
        for waypoint in route.waypoints
    )


def select_routes(
    map_: carla.Map,
    spawn_points: list[carla.Transform],
    route_count: int,
    point_count: int,
    waypoint_step_m: float,
    selection_seed: int,
    minimum_start_separation_m: float,
) -> tuple[list[SelectedRoute], dict[str, object]]:
    """Choose reproducible, geographically separated paths from native spawns."""
    indexed_spawns = sorted(
        enumerate(spawn_points),
        key=lambda item: tuple(canonical_transform(item[1])[field] for field in ("x", "y", "z", "yaw")),
    )
    spawn_catalogue = [canonical_transform(transform) for _, transform in indexed_spawns]
    catalogue_sha256 = hashlib.sha256(
        json.dumps(spawn_catalogue, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    randomizer = random.Random(selection_seed)
    randomizer.shuffle(indexed_spawns)
    selected: list[SelectedRoute] = []
    signatures: set[tuple[tuple[int, int, int, float], ...]] = set()
    rejected: dict[str, int] = {"too_close_to_selected_start": 0, "not_long_enough": 0, "duplicate_route": 0}

    # Prefer well-separated starts first.  If the map does not offer enough of
    # them, a second pass only relaxes that ergonomic selection preference, not
    # connectivity or the requested route length.
    for required_separation in (minimum_start_separation_m, 0.0):
        for spawn_index, spawn_transform in indexed_spawns:
            if len(selected) == route_count:
                break
            if any(
                distance_2d(spawn_transform.location, chosen.spawn_transform.location) < required_separation
                for chosen in selected
            ):
                rejected["too_close_to_selected_start"] += 1
                continue
            branch_seed = selection_seed + 100_003 * (spawn_index + 1) + len(selected)
            candidate = make_connected_route(
                map_, spawn_index, spawn_transform, waypoint_step_m, point_count, branch_seed
            )
            if candidate is None:
                rejected["not_long_enough"] += 1
                continue
            signature = route_signature(candidate)
            if signature in signatures:
                rejected["duplicate_route"] += 1
                continue
            candidate.route_id = f"route_{len(selected) + 1:02d}"
            selected.append(candidate)
            signatures.add(signature)
        if len(selected) == route_count:
            break
    if len(selected) != route_count:
        raise RuntimeError(
            f"could select {route_count} distinct connected routes; only selected {len(selected)}"
        )
    return selected, {
        "method": "seeded native spawn-point selection + direct Waypoint.next(waypoint_step_m)",
        "selection_seed": selection_seed,
        "native_spawn_point_count": len(spawn_points),
        "sorted_spawn_catalogue_sha256": catalogue_sha256,
        "minimum_start_separation_m_requested": minimum_start_separation_m,
        "rejections": rejected,
    }


def route_length_m(waypoints: Iterable[carla.Waypoint]) -> tuple[float, list[float]]:
    waypoint_list = list(waypoints)
    gaps = [
        float(first.transform.location.distance(second.transform.location))
        for first, second in zip(waypoint_list, waypoint_list[1:])
    ]
    return sum(gaps), gaps


def validate_route(route: SelectedRoute, waypoint_step_m: float, minimum_point_count: int) -> dict[str, object]:
    """Prove each stored successor still appears in direct map adjacency."""
    connected_edges: list[bool] = []
    for current, successor in zip(route.waypoints, route.waypoints[1:]):
        next_candidates = current.next(waypoint_step_m)
        connected_edges.append(
            any(
                int(candidate.id) == int(successor.id)
                and candidate.transform.location.distance(successor.transform.location) < 0.05
                for candidate in next_candidates
            )
        )
    length_m, gaps = route_length_m(route.waypoints)
    return {
        "minimum_waypoint_count": minimum_point_count,
        "waypoint_count": len(route.waypoints),
        "has_at_least_minimum_waypoints": len(route.waypoints) >= minimum_point_count,
        "edge_check_method": "successor membership in predecessor.next(waypoint_step_m)",
        "connected_edge_count": sum(connected_edges),
        "expected_edge_count": max(0, len(route.waypoints) - 1),
        "all_edges_connected": all(connected_edges),
        "length_m": length_m,
        "segment_lengths_m": gaps,
        "maximum_segment_length_m": max(gaps, default=0.0),
        "start_is_native_spawn_anchor": True,
        "status": "passed"
        if len(route.waypoints) >= minimum_point_count and all(connected_edges)
        else "failed",
    }


def route_document(
    route: SelectedRoute,
    map_name: str,
    waypoint_step_m: float,
    selection_seed: int,
    validation: dict[str, object],
) -> dict[str, object]:
    waypoints = [waypoint_to_dict(waypoint, order) for order, waypoint in enumerate(route.waypoints)]
    return {
        "schema_version": 1,
        "route_id": route.route_id,
        "map_name": map_name,
        "provenance": {
            "selection_method": "native spawn point followed by direct Waypoint.next() edges",
            "selection_seed": selection_seed,
            "branch_seed": route.branch_seed,
            "spawn_point_index_in_carla_map": route.spawn_index,
            "waypoint_step_m": waypoint_step_m,
        },
        "spawn_transform": transform_to_dict(route.spawn_transform),
        "start": waypoints[0],
        "finish": waypoints[-1],
        "length_m": validation["length_m"],
        "waypoint_count": len(waypoints),
        "waypoints": waypoints,
        "branch_choices": route.branch_choices,
        "connectivity_validation": validation,
        "autopilot_status": "not_run_in_route_selection_probe",
    }


def draw_route_overlays(
    world: carla.World,
    routes: list[SelectedRoute],
    lifetime_seconds: float,
    *,
    color_offset: int = 0,
) -> dict[str, object]:
    """Draw only routes, suitable for a legible map-wide route overview."""
    debug = world.debug
    for route_number, route in enumerate(routes):
        color = ROUTE_COLORS[(route_number + color_offset) % len(ROUTE_COLORS)]
        points = [waypoint.transform.location + carla.Location(z=0.6) for waypoint in route.waypoints]
        for point in points:
            debug.draw_point(point, 1.8, color, lifetime_seconds, False)
        for first, second in zip(points, points[1:]):
            debug.draw_line(first, second, 1.2, color, lifetime_seconds, False)
        # The start/finish dots are deliberately larger than ordinary route
        # samples, so they remain identifiable in the saved top-down view.
        debug.draw_point(points[0], 3.2, color, lifetime_seconds, False)
        debug.draw_point(points[-1], 3.2, color, lifetime_seconds, False)
        debug.draw_string(
            points[0] + carla.Location(z=2.0),
            f"{route.route_id} start",
            False,
            color,
            lifetime_seconds,
            False,
        )
        debug.draw_string(
            points[-1] + carla.Location(z=2.0),
            f"{route.route_id} finish",
            False,
            color,
            lifetime_seconds,
            False,
        )
    return {
        "route_point_count": sum(len(route.waypoints) for route in routes),
        "route_line_count": sum(max(0, len(route.waypoints) - 1) for route in routes),
        "route_label_count": 2 * len(routes),
    }


def draw_debug_overlays(
    world: carla.World,
    all_waypoints: list[carla.Waypoint],
    routes: list[SelectedRoute],
    lifetime_seconds: float,
) -> dict[str, object]:
    """Draw the complete finite sample and emphasize the five routes."""
    debug = world.debug
    sample_color = carla.Color(110, 110, 110)
    for waypoint in all_waypoints:
        location = waypoint.transform.location + carla.Location(z=0.25)
        # A quarter-metre point stays unobtrusive, while still being visible in
        # the map-wide 1024 px overview (Town01 spans roughly 400 m).
        debug.draw_point(location, 0.25, sample_color, lifetime_seconds, False)
    result = {
        "api": "carla.DebugHelper.draw_point/draw_line/draw_string",
        "all_waypoint_points_drawn": len(all_waypoints),
        "lifetime_seconds": lifetime_seconds,
        "persistent_lines": False,
    }
    result.update(draw_route_overlays(world, routes, lifetime_seconds))
    return result


def await_sensor_frame(images: queue.Queue[carla.Image], expected_frame: int, timeout: float) -> carla.Image:
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"timed out waiting for camera frame {expected_frame}")
        image = images.get(timeout=remaining)
        if image.frame == expected_frame:
            return image


def capture_topdown_overview(
    world: carla.World,
    coverage_waypoints: list[carla.Waypoint],
    destination: Path,
    width: int,
    height: int,
    fov: float,
    timeout: float,
) -> dict[str, object]:
    locations = [waypoint.transform.location for waypoint in coverage_waypoints]
    min_x, max_x = min(location.x for location in locations), max(location.x for location in locations)
    min_y, max_y = min(location.y for location in locations), max(location.y for location in locations)
    span_x, span_y = float(max_x - min_x), float(max_y - min_y)
    half_vertical_span = max(span_y / 2.0, (span_x / 2.0) / (width / height))
    camera_height = max(100.0, half_vertical_span / math.tan(math.radians(fov / 2.0)) * 1.15)
    transform = carla.Transform(
        carla.Location(x=(min_x + max_x) / 2.0, y=(min_y + max_y) / 2.0, z=camera_height),
        carla.Rotation(pitch=-90.0),
    )
    camera_bp = world.get_blueprint_library().find("sensor.camera.rgb")
    camera_bp.set_attribute("image_size_x", str(width))
    camera_bp.set_attribute("image_size_y", str(height))
    camera_bp.set_attribute("fov", str(fov))
    camera_bp.set_attribute("sensor_tick", "0.0")
    image_queue: queue.Queue[carla.Image] = queue.Queue()
    camera = world.spawn_actor(camera_bp, transform)
    try:
        camera.listen(image_queue.put)
        frame = world.tick()
        image = await_sensor_frame(image_queue, frame, timeout)
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save_to_disk(str(destination))
        if destination.read_bytes()[:8] != PNG_SIGNATURE:
            raise RuntimeError(f"overview image is not a PNG: {destination}")
        return {
            "path": str(destination),
            "frame": int(image.frame),
            "timestamp": float(image.timestamp),
            "width": int(image.width),
            "height": int(image.height),
            "fov_degrees": fov,
            "transform": transform_to_dict(transform),
            "network_bounds_m": {
                "min_x": float(min_x),
                "max_x": float(max_x),
                "min_y": float(min_y),
                "max_y": float(max_y),
                "span_x": span_x,
                "span_y": span_y,
            },
        }
    finally:
        camera.stop()
        camera.destroy()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--map-name", default="Town01_Opt")
    parser.add_argument("--waypoint-step-m", type=float, default=2.0)
    parser.add_argument("--route-point-count", type=int, default=60)
    parser.add_argument("--route-count", type=int, default=5)
    parser.add_argument("--selection-seed", type=int, default=20260917)
    parser.add_argument("--minimum-start-separation-m", type=float, default=60.0)
    parser.add_argument("--debug-lifetime-seconds", type=float, default=20.0)
    parser.add_argument("--overview-width", type=int, default=1024)
    parser.add_argument("--overview-height", type=int, default=1024)
    parser.add_argument("--overview-fov", type=float, default=90.0)
    args = parser.parse_args()

    if args.waypoint_step_m <= 0:
        raise SystemExit("--waypoint-step-m must be positive")
    if args.route_point_count < 10:
        raise SystemExit("--route-point-count must be at least 10")
    if args.route_count != 5:
        raise SystemExit("Stage 2 requires exactly five routes; pass --route-count 5")
    if args.debug_lifetime_seconds <= 0:
        raise SystemExit("--debug-lifetime-seconds must be positive")

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
            (map_name for map_name in available_maps if short_map_name(map_name).lower() == args.map_name.lower()),
            None,
        )
        if resolved_map is None:
            raise RuntimeError(f"{args.map_name} was not returned by get_available_maps: {available_maps}")
        world = client.load_world(resolved_map, reset_settings=False, map_layers=carla.MapLayer.All)
        original_settings = configure_synchronous_world(world)
        map_ = world.get_map()
        if short_map_name(map_.name).lower() != "town01_opt":
            raise RuntimeError(f"loaded {map_.name!r}, expected Town01_Opt")
        road_line_operation = hide_road_lines(world)

        all_waypoints = sorted(map_.generate_waypoints(args.waypoint_step_m), key=waypoint_sort_key)
        driving_waypoints = [
            waypoint for waypoint in all_waypoints if waypoint.lane_type == carla.LaneType.Driving
        ]
        if not all_waypoints or not driving_waypoints:
            raise RuntimeError("Town01_Opt returned no usable waypoints at the selected resolution")
        spawn_points = list(map_.get_spawn_points())
        if not spawn_points:
            raise RuntimeError("Town01_Opt returned no native vehicle spawn points")
        routes, selection = select_routes(
            map_,
            spawn_points,
            args.route_count,
            args.route_point_count,
            args.waypoint_step_m,
            args.selection_seed,
            args.minimum_start_separation_m,
        )
        validations = {
            route.route_id: validate_route(route, args.waypoint_step_m, minimum_point_count=10)
            for route in routes
        }
        if not all(validation["status"] == "passed" for validation in validations.values()):
            raise RuntimeError(f"route connectivity validation failed: {validations}")

        network_sample = {
            "schema_version": 1,
            "map_name": map_.name,
            "waypoint_step_m": args.waypoint_step_m,
            "sample_definition": (
                "Complete finite result of Map.generate_waypoints(waypoint_step_m), "
                "sorted by road/section/lane/s/location."
            ),
            "waypoint_count": len(all_waypoints),
            "driving_waypoint_count": len(driving_waypoints),
            "waypoints": [waypoint_to_dict(waypoint, order) for order, waypoint in enumerate(all_waypoints)],
        }
        write_json(run_dir / "network_waypoints.json", network_sample)
        route_documents = {
            route.route_id: route_document(
                route, map_.name, args.waypoint_step_m, args.selection_seed, validations[route.route_id]
            )
            for route in routes
        }
        for route_id, document in route_documents.items():
            write_json(run_dir / "routes" / f"{route_id}.json", document)
        route_index = {
            "schema_version": 1,
            "map_name": map_.name,
            "route_count": len(routes),
            "waypoint_step_m": args.waypoint_step_m,
            "selection": selection,
            "routes": [
                {
                    "route_id": route.route_id,
                    "path": f"routes/{route.route_id}.json",
                    "waypoint_count": len(route.waypoints),
                    "length_m": validations[route.route_id]["length_m"],
                    "start": location_to_dict(route.waypoints[0].transform.location),
                    "finish": location_to_dict(route.waypoints[-1].transform.location),
                }
                for route in routes
            ],
        }
        write_json(run_dir / "routes.json", route_index)

        debug_draw = draw_debug_overlays(world, all_waypoints, routes, args.debug_lifetime_seconds)
        network_overview = capture_topdown_overview(
            world,
            all_waypoints,
            run_dir / "previews" / "network_and_routes_debug_overview.png",
            args.overview_width,
            args.overview_height,
            args.overview_fov,
            args.timeout,
        )
        network_overview["path"] = "previews/network_and_routes_debug_overview.png"

        # This probe loaded a fresh world and created the preceding debug
        # shapes itself.  Clear them before producing a route-only view and
        # before returning control to a later recording stage.
        world.debug.clear_debug_shape()
        world.debug.clear_debug_string()
        route_only_draw = draw_route_overlays(world, routes, args.debug_lifetime_seconds)
        route_overview = capture_topdown_overview(
            world,
            all_waypoints,
            run_dir / "previews" / "routes_debug_overview.png",
            args.overview_width,
            args.overview_height,
            args.overview_fov,
            args.timeout,
        )
        route_overview["path"] = "previews/routes_debug_overview.png"
        world.debug.clear_debug_shape()
        world.debug.clear_debug_string()

        per_route_overviews: dict[str, dict[str, object]] = {}
        for route_number, route in enumerate(routes):
            per_route_draw = draw_route_overlays(
                world,
                [route],
                args.debug_lifetime_seconds,
                color_offset=route_number,
            )
            route_path = run_dir / "previews" / "routes" / f"{route.route_id}_debug.png"
            route_overview_image = capture_topdown_overview(
                world,
                route.waypoints,
                route_path,
                args.overview_width,
                args.overview_height,
                args.overview_fov,
                args.timeout,
            )
            route_overview_image["path"] = route_path.relative_to(run_dir).as_posix()
            per_route_overviews[route.route_id] = {
                "drawing": per_route_draw,
                "overview": route_overview_image,
            }
            world.debug.clear_debug_shape()
            world.debug.clear_debug_string()
        debug_draw["network_and_routes_overview"] = network_overview
        debug_draw["route_only_draw"] = route_only_draw
        debug_draw["route_only_overview"] = route_overview
        debug_draw["per_route_overviews"] = per_route_overviews
        debug_draw["cleanup"] = (
            "All shapes were non-persistent; clear_debug_shape() and clear_debug_string() "
            "were also called after each saved overview."
        )
        write_json(run_dir / "debug_visualization.json", debug_draw)

        validation = {
            "status": "passed",
            "checks": {
                "actual_map_is_town01_opt": short_map_name(map_.name).lower() == "town01_opt",
                "road_lines_were_hidden": road_line_operation["applied"] is True,
                "complete_waypoint_sample_is_nonempty": len(all_waypoints) > 0,
                "complete_driving_waypoint_sample_is_nonempty": len(driving_waypoints) > 0,
                "exactly_five_routes": len(routes) == 5,
                "each_route_has_at_least_ten_waypoints": all(
                    validation["has_at_least_minimum_waypoints"] for validation in validations.values()
                ),
                "each_route_has_direct_next_api_connectivity": all(
                    validation["all_edges_connected"] for validation in validations.values()
                ),
                "route_starts_are_distinct": len({route.spawn_index for route in routes}) == len(routes),
                "debug_overview_is_png": (run_dir / "previews" / "routes_debug_overview.png").read_bytes()[:8]
                == PNG_SIGNATURE,
                "all_per_route_debug_overviews_are_png": all(
                    (run_dir / str(item["overview"]["path"])).read_bytes()[:8] == PNG_SIGNATURE
                    for item in per_route_overviews.values()
                ),
                "debug_drawings_are_temporary": debug_draw["persistent_lines"] is False,
            },
            "route_validations": validations,
            "scope": (
                "Route construction and DebugHelper visualization only. No vehicle was spawned, "
                "no Traffic Manager path was submitted, and no drive/completion claim is made."
            ),
        }
        write_json(run_dir / "validation.json", validation)
        update_metadata(
            metadata_path,
            state="running",
            carla_client_version=client.get_client_version(),
            carla_server_version=client.get_server_version(),
            map_name=map_.name,
            road_line_operation=road_line_operation,
            route_selection={
                "route_count": len(routes),
                "route_point_count": args.route_point_count,
                "waypoint_step_m": args.waypoint_step_m,
                "selection_seed": args.selection_seed,
                "route_index_path": "routes.json",
                "network_sample_path": "network_waypoints.json",
                "debug_visualization_path": "debug_visualization.json",
            },
            validation_path="validation.json",
            validation_status=validation["status"],
        )
        print(run_dir / "routes.json")
    except Exception as exc:
        update_metadata(metadata_path, state="failed", stage2_routes_error=str(exc))
        raise
    finally:
        if world is not None and original_settings is not None:
            restore_world_settings(world, original_settings)


if __name__ == "__main__":
    main()
