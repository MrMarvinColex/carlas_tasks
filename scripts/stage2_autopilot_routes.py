#!/usr/bin/env python3
"""Drive approved Stage-2 routes using CARLA Traffic Manager.

The script is deliberately limited to route/autopilot validation: it spawns
one ego vehicle at a time, submits the approved route instructions or waypoint
locations to Traffic Manager, records its trajectory and collision events, and applies
explicit completion/timeout/stuck criteria. It does not create the Stage-3
camera rig or dataset images.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
import carla

from stage2_routes import (
    configure_synchronous_world,
    hide_road_lines,
    location_to_dict,
    restore_world_settings,
    short_map_name,
    transform_to_dict,
    update_metadata,
    write_json,
)


@dataclass
class RouteDefinition:
    route_id: str
    source_path: Path
    source_document: dict[str, object]
    dense_waypoints: list[carla.Waypoint]
    adaptive_waypoints: list[carla.Waypoint]
    dense_locations: list[carla.Location]
    adaptive_locations: list[carla.Location]
    cumulative_dense_m: list[float]
    length_m: float
    traffic_manager_route_instructions: list[str]


def distance_2d(first: carla.Location, second: carla.Location) -> float:
    return math.hypot(float(first.x - second.x), float(first.y - second.y))


def normalise_heading_delta_deg(delta: float) -> float:
    """Return a CARLA yaw difference in [-180, 180]."""
    return (delta + 180.0) % 360.0 - 180.0


def derive_traffic_manager_instructions(
    dense_waypoints: list[carla.Waypoint],
) -> list[str]:
    """Translate each contiguous junction traversal into TM's Left/Right/Straight.

    ``TrafficManager.set_route`` accepts decisions, rather than coordinates.  A
    junction can span many two-metre samples, so derive exactly one decision per
    contiguous ``is_junction`` group, comparing the lane heading immediately
    before and after that group.
    """
    groups: list[tuple[int, int]] = []
    group_start: int | None = None
    for index, waypoint in enumerate(dense_waypoints):
        if waypoint.is_junction and group_start is None:
            group_start = index
        elif not waypoint.is_junction and group_start is not None:
            groups.append((group_start, index - 1))
            group_start = None
    if group_start is not None:
        groups.append((group_start, len(dense_waypoints) - 1))

    instructions: list[str] = []
    for start, end in groups:
        before = max(0, start - 1)
        after = min(len(dense_waypoints) - 1, end + 1)
        delta = normalise_heading_delta_deg(
            float(dense_waypoints[after].transform.rotation.yaw)
            - float(dense_waypoints[before].transform.rotation.yaw)
        )
        if delta <= -35.0:
            instructions.append("Left")
        elif delta >= 35.0:
            instructions.append("Right")
        else:
            instructions.append("Straight")
    return instructions


def speed_mps(vehicle: carla.Vehicle) -> float:
    velocity = vehicle.get_velocity()
    return math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)


def location_from_dict(value: dict[str, object]) -> carla.Location:
    return carla.Location(
        x=float(value["x"]), y=float(value["y"]), z=float(value["z"])
    )


def load_route(
    map_: carla.Map,
    source_path: Path,
    expected_map_name: str,
    dense_step_m: float,
) -> RouteDefinition:
    document = json.loads(source_path.read_text())
    if short_map_name(str(document["map_name"])).lower() != expected_map_name.lower():
        raise RuntimeError(f"{source_path.name} names another map: {document['map_name']}")
    route_id = str(document.get("candidate_id") or source_path.stem)
    dense_document = document["dense_reference"]
    if abs(float(dense_document["step_m"]) - dense_step_m) > 1e-6:
        raise RuntimeError(f"{route_id} has unexpected dense step")
    dense_waypoints: list[carla.Waypoint] = []
    for item in dense_document["waypoints"]:
        waypoint = map_.get_waypoint_xodr(
            int(item["road_id"]), int(item["lane_id"]), float(item["s"])
        )
        if waypoint is None or int(waypoint.id) != int(item["waypoint_id"]):
            raise RuntimeError(f"{route_id} dense waypoint identity could not be reconstructed")
        dense_waypoints.append(waypoint)
    if len(dense_waypoints) < 10:
        raise RuntimeError(f"{route_id} has fewer than ten dense waypoints")
    for first, second in zip(dense_waypoints, dense_waypoints[1:]):
        successors = first.next(dense_step_m)
        if not any(int(candidate.id) == int(second.id) for candidate in successors):
            raise RuntimeError(f"{route_id} has a disconnected dense edge")

    adaptive_indices = [int(index) for index in document["adaptive_proposal"]["dense_indices"]]
    if len(adaptive_indices) < 10 or adaptive_indices != sorted(set(adaptive_indices)):
        raise RuntimeError(f"{route_id} has an invalid adaptive index list")
    if adaptive_indices[0] != 0 or adaptive_indices[-1] != len(dense_waypoints) - 1:
        raise RuntimeError(f"{route_id} adaptive path does not cover its endpoints")
    adaptive_waypoints = [dense_waypoints[index] for index in adaptive_indices]

    dense_locations = [waypoint.transform.location for waypoint in dense_waypoints]
    cumulative = [0.0]
    for first, second in zip(dense_locations, dense_locations[1:]):
        cumulative.append(cumulative[-1] + distance_2d(first, second))
    stored_length = float(document["length_m"])
    if abs(cumulative[-1] - stored_length) > 0.25:
        raise RuntimeError(f"{route_id} stored and reconstructed lengths differ")
    return RouteDefinition(
        route_id=route_id,
        source_path=source_path,
        source_document=document,
        dense_waypoints=dense_waypoints,
        adaptive_waypoints=adaptive_waypoints,
        dense_locations=dense_locations,
        adaptive_locations=[waypoint.transform.location for waypoint in adaptive_waypoints],
        cumulative_dense_m=cumulative,
        length_m=stored_length,
        traffic_manager_route_instructions=derive_traffic_manager_instructions(
            dense_waypoints
        ),
    )


def nearest_route_state(route: RouteDefinition, location: carla.Location) -> dict[str, float | int]:
    distances = [distance_2d(location, candidate) for candidate in route.dense_locations]
    index = min(range(len(distances)), key=distances.__getitem__)
    return {
        "nearest_dense_index": index,
        "nearest_route_distance_m": distances[index],
        "nearest_route_progress_m": route.cumulative_dense_m[index],
        "distance_to_finish_m": distance_2d(location, route.dense_locations[-1]),
    }


def transform_location_record(
    vehicle: carla.Vehicle,
    snapshot: carla.WorldSnapshot,
    route: RouteDefinition,
) -> dict[str, object]:
    transform = vehicle.get_transform()
    state = nearest_route_state(route, transform.location)
    return {
        "frame": int(snapshot.frame),
        "simulation_time_s": float(snapshot.timestamp.elapsed_seconds),
        "transform": transform_to_dict(transform),
        "speed_mps": speed_mps(vehicle),
        **state,
    }


def collision_record(event: carla.CollisionEvent) -> dict[str, object]:
    other = event.other_actor
    impulse = event.normal_impulse
    return {
        "frame": int(event.frame),
        "simulation_time_s": float(event.timestamp),
        "other_actor_id": int(other.id) if other is not None else None,
        "other_actor_type_id": str(other.type_id) if other is not None else None,
        "normal_impulse": {"x": float(impulse.x), "y": float(impulse.y), "z": float(impulse.z)},
    }


def choose_vehicle_blueprint(library: carla.BlueprintLibrary) -> carla.ActorBlueprint:
    preferred = library.filter("vehicle.tesla.model3")
    if preferred:
        return preferred[0]
    candidates = sorted(library.filter("vehicle.*"), key=lambda item: item.id)
    if not candidates:
        raise RuntimeError("CARLA exposed no vehicle blueprints")
    return candidates[0]


def spawn_at_route_start(
    world: carla.World,
    blueprint: carla.ActorBlueprint,
    route: RouteDefinition,
) -> carla.Vehicle:
    transform = carla.Transform(
        route.dense_waypoints[0].transform.location + carla.Location(z=0.35),
        route.dense_waypoints[0].transform.rotation,
    )
    blueprint.set_attribute("role_name", "stage2_ego")
    actor = world.try_spawn_actor(blueprint, transform)
    if actor is None or not isinstance(actor, carla.Vehicle):
        raise RuntimeError(f"{route.route_id}: vehicle could not spawn at route start")
    return actor


def stop_after_completion(
    world: carla.World,
    vehicle: carla.Vehicle,
    fixed_delta_s: float,
    duration_s: float,
) -> dict[str, object]:
    braking_samples: list[float] = []
    for _ in range(max(1, round(3.0 / fixed_delta_s))):
        vehicle.apply_control(carla.VehicleControl(throttle=0.0, brake=1.0, hand_brake=True))
        world.tick()
        braking_samples.append(speed_mps(vehicle))
    before = vehicle.get_transform().location
    stationary_samples: list[float] = []
    for _ in range(max(1, round(duration_s / fixed_delta_s))):
        vehicle.apply_control(carla.VehicleControl(throttle=0.0, brake=1.0, hand_brake=True))
        world.tick()
        stationary_samples.append(speed_mps(vehicle))
    after = vehicle.get_transform().location
    return {
        "braking_duration_s": 3.0,
        "observation_duration_s": duration_s,
        "displacement_m": distance_2d(before, after),
        "maximum_braking_speed_mps": max(braking_samples),
        "maximum_stationary_speed_mps": max(stationary_samples),
        "stopped": max(stationary_samples) <= 0.5 and distance_2d(before, after) <= 0.25,
    }


def drive_route(
    world: carla.World,
    traffic_manager: carla.TrafficManager,
    traffic_manager_port: int,
    blueprint: carla.ActorBlueprint,
    route: RouteDefinition,
    run_dir: Path,
    fixed_delta_s: float,
    finish_radius_m: float,
    timeout_s: float,
    stuck_window_s: float,
    stuck_grace_s: float,
    path_deviation_limit_m: float,
    traffic_manager_command: str,
) -> dict[str, object]:
    route_dir = run_dir / "drives" / route.route_id
    collisions: list[dict[str, object]] = []
    vehicle: carla.Vehicle | None = None
    collision_sensor: carla.Sensor | None = None
    trajectory: list[dict[str, object]] = []
    started_wall = time.monotonic()
    try:
        vehicle = spawn_at_route_start(world, blueprint, route)
        collision_blueprint = world.get_blueprint_library().find("sensor.other.collision")
        collision_sensor = world.spawn_actor(
            collision_blueprint,
            carla.Transform(),
            attach_to=vehicle,
        )
        collision_sensor.listen(lambda event: collisions.append(collision_record(event)))
        world.tick()

        traffic_manager.auto_lane_change(vehicle, False)
        traffic_manager.ignore_lights_percentage(vehicle, 100.0)
        traffic_manager.ignore_signs_percentage(vehicle, 100.0)
        traffic_manager.vehicle_percentage_speed_difference(vehicle, -20.0)
        vehicle.set_autopilot(True, traffic_manager_port)
        if traffic_manager_command == "set_route":
            # set_route accepts one choice per intersection.  It avoids an
            # observed set_path failure where a valid coordinate chain was
            # accepted but Traffic Manager took a different later branch.
            traffic_manager.set_route(vehicle, route.traffic_manager_route_instructions)
            submitted_value: list[object] = route.traffic_manager_route_instructions
        elif traffic_manager_command == "set_path":
            # The complete 2 m chain is retained as an alternate, documented
            # CARLA mechanism.  It is intentionally not the default after the
            # branch-following pilot described above.
            traffic_manager.set_path(vehicle, route.dense_locations[1:])
            submitted_value = [location_to_dict(location) for location in route.dense_locations[1:]]
        else:
            raise RuntimeError(f"unsupported Traffic Manager command: {traffic_manager_command}")

        initial_snapshot = world.get_snapshot()
        initial_record = transform_location_record(vehicle, initial_snapshot, route)
        trajectory.append(initial_record)
        simulation_start = float(initial_snapshot.timestamp.elapsed_seconds)
        history: collections.deque[dict[str, object]] = collections.deque([initial_record])
        maximum_deviation_m = float(initial_record["nearest_route_distance_m"])
        maximum_progress_m = float(initial_record["nearest_route_progress_m"])
        outcome = "timeout"
        completion_record: dict[str, object] | None = None
        stuck_diagnostic: dict[str, object] | None = None

        while True:
            frame = world.tick()
            snapshot = world.get_snapshot()
            if int(snapshot.frame) != int(frame):
                raise RuntimeError("world snapshot frame does not match tick frame")
            record = transform_location_record(vehicle, snapshot, route)
            trajectory.append(record)
            elapsed_s = float(record["simulation_time_s"]) - simulation_start
            maximum_deviation_m = max(maximum_deviation_m, float(record["nearest_route_distance_m"]))
            if float(record["nearest_route_distance_m"]) <= path_deviation_limit_m:
                maximum_progress_m = max(maximum_progress_m, float(record["nearest_route_progress_m"]))
            history.append(record)
            while (
                len(history) > 1
                and float(record["simulation_time_s"]) - float(history[0]["simulation_time_s"])
                > stuck_window_s
            ):
                history.popleft()

            required_progress = route.length_m * 0.95
            if (
                float(record["distance_to_finish_m"]) <= finish_radius_m
                and maximum_progress_m >= required_progress
            ):
                outcome = "completed"
                completion_record = record
                break
            if collisions:
                outcome = "collision"
                break
            if elapsed_s >= timeout_s:
                outcome = "timeout"
                break
            if elapsed_s >= stuck_grace_s and len(history) > 1:
                oldest = history[0]
                moved_m = distance_2d(
                    location_from_dict(oldest["transform"]["location"]),
                    location_from_dict(record["transform"]["location"]),
                )
                progress_gain_m = float(record["nearest_route_progress_m"]) - float(
                    oldest["nearest_route_progress_m"]
                )
                speeds = [float(item["speed_mps"]) for item in history]
                if moved_m < 1.0 and progress_gain_m < 0.5 and max(speeds) < 0.5:
                    outcome = "stuck"
                    stuck_diagnostic = {
                        "window_s": float(record["simulation_time_s"]) - float(oldest["simulation_time_s"]),
                        "moved_m": moved_m,
                        "progress_gain_m": progress_gain_m,
                        "maximum_speed_mps": max(speeds),
                    }
                    break

        vehicle.set_autopilot(False, traffic_manager_port)
        post_finish = stop_after_completion(world, vehicle, fixed_delta_s, duration_s=1.0)
        final_snapshot = world.get_snapshot()
        final_record = transform_location_record(vehicle, final_snapshot, route)
        trajectory.append(final_record)
        route_dir.mkdir(parents=True, exist_ok=True)
        write_json(route_dir / "trajectory.json", trajectory)
        write_json(route_dir / "collisions.json", collisions)
        result = {
            "route_id": route.route_id,
            "source_route_file": route.source_path.as_posix(),
            "vehicle_blueprint": blueprint.id,
            "vehicle_id": int(vehicle.id),
            "traffic_manager_command": traffic_manager_command,
            "traffic_manager_submitted_value": submitted_value,
            "traffic_manager_route_instruction_count": len(route.traffic_manager_route_instructions),
            "traffic_manager_path_location_count": (
                len(route.dense_locations) - 1 if traffic_manager_command == "set_path" else 0
            ),
            "dense_waypoint_count": len(route.dense_waypoints),
            "adaptive_waypoint_count": len(route.adaptive_waypoints),
            "route_length_m": route.length_m,
            "finish_radius_m": finish_radius_m,
            "timeout_s": timeout_s,
            "stuck_window_s": stuck_window_s,
            "started_simulation_time_s": simulation_start,
            "ended_simulation_time_s": float(final_record["simulation_time_s"]),
            "wall_time_s": time.monotonic() - started_wall,
            "outcome": outcome,
            "completion_record": completion_record,
            "stuck_diagnostic": stuck_diagnostic,
            "collision_count": len(collisions),
            "maximum_deviation_m": maximum_deviation_m,
            "maximum_progress_m": maximum_progress_m,
            "required_completion_progress_m": route.length_m * 0.95,
            "final_record": final_record,
            "post_finish_stop": post_finish,
            "checks": {
                "vehicle_spawned": True,
                "traffic_manager_command_submitted": True,
                "completion_radius_reached": outcome == "completed",
                "completed_without_collision": outcome == "completed" and not collisions,
                "not_stuck": outcome != "stuck",
                "not_timed_out": outcome != "timeout",
                "post_finish_vehicle_stopped": bool(post_finish["stopped"]),
                "route_deviation_within_limit": maximum_deviation_m <= path_deviation_limit_m,
            },
        }
        write_json(route_dir / "result.json", result)
        return result
    finally:
        if collision_sensor is not None:
            collision_sensor.stop()
            collision_sensor.destroy()
        if vehicle is not None:
            vehicle.destroy()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument(
        "--routes-run",
        type=Path,
        default=Path("runs/20260919T154916Z-route-numbering-swap-b5e941"),
    )
    parser.add_argument("--route-id", action="append", default=[])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--traffic-manager-port", type=int, default=8000)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--map-name", default="Town01_Opt")
    parser.add_argument("--dense-step-m", type=float, default=2.0)
    parser.add_argument("--finish-radius-m", type=float, default=8.0)
    parser.add_argument("--route-timeout-s", type=float, default=150.0)
    parser.add_argument("--stuck-window-s", type=float, default=10.0)
    parser.add_argument("--stuck-grace-s", type=float, default=15.0)
    parser.add_argument("--path-deviation-limit-m", type=float, default=15.0)
    parser.add_argument(
        "--traffic-manager-command",
        choices=("set_route", "set_path"),
        default="set_route",
        help="CARLA Traffic Manager routing API to validate.",
    )
    args = parser.parse_args()
    if args.finish_radius_m <= 0.0 or args.route_timeout_s <= 0.0:
        raise SystemExit("finish radius and route timeout must be positive")

    run_dir = args.run_dir.resolve()
    routes_run = args.routes_run.resolve()
    metadata_path = run_dir / "metadata.json"
    routes_index_path = routes_run / "revised_routes.json"
    if not metadata_path.is_file():
        raise SystemExit(f"run directory was not created by create_run.py: {run_dir}")
    if not routes_index_path.is_file():
        raise SystemExit(f"approved route index is missing: {routes_index_path}")
    index = json.loads(routes_index_path.read_text())
    available = {str(item["route_id"]): item for item in index["routes"]}
    requested_ids = args.route_id or list(available)
    unknown = sorted(set(requested_ids) - set(available))
    if unknown:
        raise SystemExit(f"unknown route IDs: {unknown}")

    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout)
    world: carla.World | None = None
    traffic_manager: carla.TrafficManager | None = None
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
        if short_map_name(map_.name).lower() != args.map_name.lower():
            raise RuntimeError(f"loaded {map_.name!r}, expected {args.map_name}")
        road_line_operation = hide_road_lines(world)
        traffic_manager = client.get_trafficmanager(args.traffic_manager_port)
        traffic_manager.set_synchronous_mode(True)
        traffic_manager.set_random_device_seed(2026091905)
        blueprint = choose_vehicle_blueprint(world.get_blueprint_library())
        routes = [
            load_route(
                map_,
                routes_run / str(available[route_id]["path"]),
                args.map_name,
                args.dense_step_m,
            )
            for route_id in requested_ids
        ]
        drive_config = {
            "approved_routes_run": routes_run.relative_to(Path.cwd()).as_posix(),
            "selected_route_ids": requested_ids,
            "map_name": map_.name,
            "dense_step_m": args.dense_step_m,
            "fixed_delta_seconds": 0.05,
            "traffic_manager_port": args.traffic_manager_port,
            "vehicle_blueprint": blueprint.id,
            "traffic_manager_command": args.traffic_manager_command,
            "finish_radius_m": args.finish_radius_m,
            "route_timeout_s": args.route_timeout_s,
            "stuck_window_s": args.stuck_window_s,
            "stuck_grace_s": args.stuck_grace_s,
            "path_deviation_limit_m": args.path_deviation_limit_m,
            "road_line_operation": road_line_operation,
        }
        write_json(run_dir / "drive_config.json", drive_config)
        results = [
            drive_route(
                world,
                traffic_manager,
                args.traffic_manager_port,
                blueprint,
                route,
                run_dir,
                0.05,
                args.finish_radius_m,
                args.route_timeout_s,
                args.stuck_window_s,
                args.stuck_grace_s,
                args.path_deviation_limit_m,
                args.traffic_manager_command,
            )
            for route in routes
        ]
        all_checks = [
            result["outcome"] == "completed" and all(result["checks"].values())
            for result in results
        ]
        validation = {
            "status": "passed" if all(all_checks) else "failed",
            "checks": {
                "actual_map_is_town01_opt": short_map_name(map_.name).lower() == "town01_opt",
                "road_lines_were_hidden": road_line_operation["applied"] is True,
                "requested_routes_were_driven": len(results) == len(requested_ids),
                "all_routes_completed": all(result["outcome"] == "completed" for result in results),
                "all_routes_passed_completion_and_safety_checks": all(all_checks),
            },
            "route_results": results,
            "scope": "Stage-2 Traffic Manager/autopilot validation only; no cameras or dataset recording.",
        }
        write_json(run_dir / "validation.json", validation)
        update_metadata(
            metadata_path,
            state="running",
            carla_client_version=client.get_client_version(),
            carla_server_version=client.get_server_version(),
            map_name=map_.name,
            road_line_operation=road_line_operation,
            approved_routes_run=str(routes_run),
            traffic_manager_port=args.traffic_manager_port,
            validation_path="validation.json",
            validation_status=validation["status"],
        )
        if validation["status"] != "passed":
            raise RuntimeError(f"autopilot validation failed: {[result['outcome'] for result in results]}")
        print(run_dir / "validation.json")
    except Exception as exc:
        update_metadata(metadata_path, state="failed", stage2_autopilot_error=str(exc))
        raise
    finally:
        if traffic_manager is not None:
            traffic_manager.set_synchronous_mode(False)
        if world is not None and original_settings is not None:
            restore_world_settings(world, original_settings)


if __name__ == "__main__":
    main()
