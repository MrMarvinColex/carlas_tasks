#!/usr/bin/env python3
"""Record one complete Stage-4 baseline drive with the validated AV2 camera rig."""
from __future__ import annotations

import argparse
import collections
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
import json
import math
import queue
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path
from typing import Any

import carla

from stage2_autopilot_routes import (
    RouteDefinition,
    choose_vehicle_blueprint,
    collision_record,
    distance_2d,
    load_route,
    location_from_dict,
    nearest_route_state,
    spawn_at_route_start,
    stop_after_completion,
)
from stage2_routes import configure_synchronous_world, hide_road_lines, restore_world_settings, short_map_name, update_metadata, write_json
from stage3_geometry import homogeneous_transform_point, rear_axle_midpoint_m
from stage3_recording import (
    CAMERA_ORDER,
    MODALITIES,
    SensorRuntime,
    applied_camera_configuration,
    directory_bytes,
    pose_from_snapshot,
    resource_sample,
    configure_sensor_blueprint,
    verify_source_files,
    write_grayscale_png,
)


@dataclass
class PendingWrite:
    """One ordered capture whose PNG encoding is running outside the tick loop."""

    sample_index: int
    future: Future[dict[str, object]]


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def write_rgb_png(path: Path, width: int, height: int, pixels: bytes) -> None:
    if len(pixels) != width * height * 3:
        raise ValueError(f"RGB buffer has {len(pixels)} bytes, expected {width * height * 3}")
    scanlines = b"".join(b"\x00" + pixels[row * width * 3 : (row + 1) * width * 3] for row in range(height))
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(scanlines, level=6))
        + png_chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def rgb_from_carla_bgra(image: carla.Image) -> bytes:
    raw = memoryview(image.raw_data)
    expected = image.width * image.height * 4
    if len(raw) != expected:
        raise ValueError(f"CARLA RGB buffer has {len(raw)} bytes, expected {expected}")
    rgb = bytearray(image.width * image.height * 3)
    rgb[0::3] = raw[2::4]
    rgb[1::3] = raw[1::4]
    rgb[2::3] = raw[0::4]
    return bytes(rgb)


def cityscapes_preview(image: carla.Image) -> bytes:
    """Apply CARLA's own palette before detaching the resulting BGRA pixels."""
    image.convert(carla.ColorConverter.CityScapesPalette)
    return rgb_from_carla_bgra(image)


def prepare_sample_buffers(
    images: dict[str, carla.Image], runtimes: dict[str, SensorRuntime]
) -> dict[str, tuple[int, int, bytes, bytes, bytes, list[int]]]:
    """Detach pixels from CARLA image objects before their asynchronous encoding."""
    prepared: dict[str, tuple[int, int, bytes, bytes, bytes, list[int]]] = {}
    for camera_name in CAMERA_ORDER:
        rgb_key, semantic_key = f"rgb:{camera_name}", f"semantic:{camera_name}"
        if rgb_key not in runtimes:
            continue
        rgb_image, semantic_image = images[rgb_key], images[semantic_key]
        class_ids = bytes(memoryview(semantic_image.raw_data)[2::4])
        prepared[camera_name] = (
            int(rgb_image.width),
            int(rgb_image.height),
            rgb_from_carla_bgra(rgb_image),
            class_ids,
            cityscapes_preview(semantic_image),
            sorted(set(class_ids)),
        )
    return prepared


def save_prepared_sample(
    run_dir: Path,
    sample_index: int,
    frame: int,
    sensor_timestamp_s: float,
    prepared: dict[str, tuple[int, int, bytes, bytes, bytes, list[int]]],
    pose: dict[str, object],
) -> dict[str, object]:
    files: dict[str, dict[str, str]] = {}
    semantic_ids: dict[str, list[int]] = {}
    stem = f"{sample_index:06d}_{frame:08d}.png"
    for camera_name, (width, height, rgb, class_ids, preview, classes) in prepared.items():
        rgb_path = run_dir / "rgb" / camera_name / stem
        semantic_path = run_dir / "semantic" / camera_name / stem
        preview_path = run_dir / "previews" / "semantic" / camera_name / stem
        write_rgb_png(rgb_path, width, height, rgb)
        write_grayscale_png(semantic_path, width, height, class_ids)
        write_rgb_png(preview_path, width, height, preview)
        for path in (rgb_path, semantic_path, preview_path):
            if not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError(f"sensor output was not written: {path}")
        files[camera_name] = {
            "rgb": rgb_path.relative_to(run_dir).as_posix(),
            "semantic_raw_ids": semantic_path.relative_to(run_dir).as_posix(),
            "semantic_preview": preview_path.relative_to(run_dir).as_posix(),
        }
        semantic_ids[camera_name] = classes
    return {
        **pose,
        "sample_index": sample_index,
        "sensor_timestamp_s": sensor_timestamp_s,
        "images": files,
        "semantic_class_ids_present": semantic_ids,
    }


def finish_one_write(
    pending_writes: collections.deque[PendingWrite],
    samples: list[dict[str, object]],
    partial_path: Path,
) -> float:
    """Commit the oldest write in capture order and return time spent backpressuring."""
    started = time.monotonic()
    pending = pending_writes.popleft()
    sample = pending.future.result()
    if int(sample["sample_index"]) != len(samples) or pending.sample_index != len(samples):
        raise RuntimeError("asynchronous writer returned captures out of order")
    samples.append(sample)
    write_json(partial_path, {"schema_version": 1, "state": "recording", "samples": samples})
    return time.monotonic() - started


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def free_gib(path: Path) -> float:
    result = __import__("shutil").disk_usage(path)
    return result.free / (1024**3)


def apply_weather(world: carla.World, profile_id: str, profile: dict[str, Any]) -> dict[str, object]:
    parameters = profile.get("parameters")
    if not isinstance(parameters, dict) or not parameters:
        raise RuntimeError(f"weather profile {profile_id} has no parameters")
    weather = world.get_weather()
    applied: dict[str, float] = {}
    for name, value in parameters.items():
        if not hasattr(weather, name):
            raise RuntimeError(f"installed CARLA weather has no parameter {name!r}")
        numeric = float(value)
        setattr(weather, name, numeric)
        applied[name] = numeric
    world.set_weather(weather)
    for _ in range(3):
        world.tick()
    return {
        "weather_id": profile_id,
        "description": str(profile.get("description", "")),
        "parameters": applied,
        "carla_weather_repr": str(world.get_weather()),
    }


def route_state(snapshot: carla.WorldSnapshot, vehicle_id: int, route: RouteDefinition) -> dict[str, object]:
    actor = snapshot.find(vehicle_id)
    if actor is None:
        raise RuntimeError(f"ego vehicle is absent from snapshot {snapshot.frame}")
    state = nearest_route_state(route, actor.get_transform().location)
    return {"frame": int(snapshot.frame), "simulation_time_s": float(snapshot.timestamp.elapsed_seconds), **state}


def drain_sensor_events(
    events: queue.Queue[tuple[str, carla.Image]],
    pending: dict[int, dict[str, carla.Image]],
    first_event_wall: dict[int, float],
    duplicate_keys: list[str],
    expected_keys: set[str],
    timeout_s: float,
) -> None:
    def add(item: tuple[str, carla.Image]) -> None:
        key, image = item
        frame = int(image.frame)
        images = pending.setdefault(frame, {})
        if key in images:
            duplicate_keys.append(f"{frame}:{key}")
        images[key] = image
        first_event_wall.setdefault(frame, time.monotonic())

    try:
        add(events.get(timeout=0.05))
    except queue.Empty:
        pass
    while True:
        try:
            add(events.get_nowait())
        except queue.Empty:
            break
    while True:
        incomplete = [frame for frame, images in pending.items() if set(images) != expected_keys]
        if not incomplete:
            return
        oldest = min(incomplete, key=first_event_wall.__getitem__)
        remaining = timeout_s - (time.monotonic() - first_event_wall[oldest])
        if remaining <= 0.0:
            missing = sorted(expected_keys - set(pending[oldest]))
            raise TimeoutError(f"sensor frame {oldest} missed {missing}")
        try:
            add(events.get(timeout=min(remaining, 0.5)))
        except queue.Empty:
            continue


def calibration_and_sensors(
    world: carla.World,
    vehicle: carla.Vehicle,
    calibration_path: Path,
    calibration: dict[str, Any],
    mount_z_offset_m: float,
    sensor_tick_s: float,
    events: queue.Queue[tuple[str, carla.Image]],
) -> tuple[list[SensorRuntime], dict[str, object]]:
    by_name = {camera["sensor_name"]: camera for camera in calibration["cameras"]}
    if set(by_name) != set(CAMERA_ORDER):
        raise RuntimeError("AV2 calibration does not contain the canonical nine-camera set")
    physics = vehicle.get_physics_control()
    wheel_positions_world_cm = [[wheel.position.x, wheel.position.y, wheel.position.z] for wheel in physics.wheels]
    inverse_vehicle_matrix = vehicle.get_transform().get_inverse_matrix()
    wheel_positions_local_m = [
        homogeneous_transform_point(inverse_vehicle_matrix, (position[0] / 100.0, position[1] / 100.0, position[2] / 100.0))
        for position in wheel_positions_world_cm
    ]
    rear_axle_origin, wheel_positions_m = rear_axle_midpoint_m(
        [[component * 100.0 for component in position] for position in wheel_positions_local_m]
    )
    bbox_centre = tuple(float(value) for value in (vehicle.bounding_box.location.x, vehicle.bounding_box.location.y, vehicle.bounding_box.location.z))
    bbox_extent = tuple(float(value) for value in (vehicle.bounding_box.extent.x, vehicle.bounding_box.extent.y, vehicle.bounding_box.extent.z))
    transforms: dict[str, carla.Transform] = {}
    applied_cameras: list[dict[str, object]] = []
    for name in CAMERA_ORDER:
        transform, applied = applied_camera_configuration(by_name[name], rear_axle_origin, mount_z_offset_m, bbox_centre, bbox_extent)
        transforms[name] = transform
        applied_cameras.append(applied)
    library = world.get_blueprint_library()
    sensors: list[SensorRuntime] = []
    for name in CAMERA_ORDER:
        applied = next(item for item in applied_cameras if item["sensor_name"] == name)
        for modality in MODALITIES:
            actor = world.spawn_actor(
                configure_sensor_blueprint(library, modality, applied, sensor_tick_s),
                transforms[name],
                attach_to=vehicle,
                attachment_type=carla.AttachmentType.Rigid,
            )
            if not isinstance(actor, carla.Sensor):
                raise RuntimeError(f"spawned actor is not a sensor: {modality}:{name}")
            key = f"{modality}:{name}"
            sensors.append(SensorRuntime(key, name, modality, actor, int(applied["image_width_px"]), int(applied["image_height_px"])))
            actor.listen(lambda image, sensor_key=key: events.put((sensor_key, image)))
    record = {
        "schema_version": 1,
        "source_calibration_path": calibration_path.relative_to(Path.cwd()).as_posix(),
        "source": calibration["source"],
        "log_id": calibration["log_id"],
        "coordinate_conversion": {
            "av2_ego_to_carla_vehicle": "(x,y,z) -> (x,-y,z)",
            "av2_optical_to_carla_camera": "(x_right,y_down,z_forward) -> (y_right,-z_up,x_forward)",
            "av2_ego_origin": "rear axle centre",
            "carla_rear_axle_origin_relative_to_actor_m": list(rear_axle_origin),
            "mount_z_offset_m": mount_z_offset_m,
            "wheel_positions_reported_by_carla_world_cm": wheel_positions_world_cm,
            "wheel_positions_relative_to_actor_m": [list(value) for value in wheel_positions_m],
        },
        "carla_vehicle": {
            "blueprint": vehicle.type_id,
            "semantic_tags_reported_by_actor": [int(tag) for tag in vehicle.semantic_tags],
            "bounding_box_centre_m": list(bbox_centre),
            "bounding_box_extent_m": list(bbox_extent),
        },
        "applied_cameras": applied_cameras,
    }
    return sensors, record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--baseline-config", type=Path, default=Path("configs/stage4_baseline_matrix.json"))
    parser.add_argument("--calibration", type=Path, default=Path("configs/av2/54bc6dbc-ebfb-3fba-b5b3-57f88b4b79ca/calibration.json"))
    parser.add_argument("--route-id", required=True)
    parser.add_argument("--weather-id", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--traffic-manager-port", type=int, default=8000)
    parser.add_argument("--sensor-timeout-s", type=float, default=30.0)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--writer-workers", type=int, default=4)
    parser.add_argument("--max-pending-write-samples", type=int, default=8)
    parser.add_argument("--resource-sample-every", type=int, default=10)
    parser.add_argument(
        "--benchmark-simulation-s",
        type=float,
        default=0.0,
        help="Record a labelled throughput benchmark instead of requiring route completion.",
    )
    args = parser.parse_args()

    if args.writer_workers <= 0 or args.max_pending_write_samples <= 0 or args.resource_sample_every <= 0:
        raise SystemExit("writer worker, pending-write, and resource-sample counts must be positive")
    if args.benchmark_simulation_s < 0.0:
        raise SystemExit("benchmark simulation duration cannot be negative")

    run_dir = args.run_dir.resolve()
    metadata_path = run_dir / "metadata.json"
    config_path = args.baseline_config.resolve()
    calibration_path = args.calibration.resolve()
    if not metadata_path.is_file():
        raise SystemExit("run directory was not created by create_run.py")
    config = load_json(config_path)
    if args.route_id not in config["route_ids"]:
        raise SystemExit(f"route is not in the fixed baseline matrix: {args.route_id}")
    profiles = config["weather_profiles"]
    if args.weather_id not in profiles:
        raise SystemExit(f"weather is not in the fixed baseline matrix: {args.weather_id}")
    available_before_gib = free_gib(run_dir)
    minimum_gib = float(config["disk_budget"]["minimum_free_gib_before_run"])
    if available_before_gib < minimum_gib:
        raise SystemExit(f"only {available_before_gib:.1f} GiB free; policy requires {minimum_gib:.1f} GiB")
    calibration = load_json(calibration_path)
    verify_source_files(calibration_path, calibration)
    routes_run = (Path.cwd() / str(config["approved_routes_run"])).resolve()
    index = load_json(routes_run / "revised_routes.json")
    route_item = next((item for item in index["routes"] if item["route_id"] == args.route_id), None)
    if route_item is None:
        raise RuntimeError(f"route missing from approved index: {args.route_id}")

    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout)
    world: carla.World | None = None
    traffic_manager: carla.TrafficManager | None = None
    original_settings: dict[str, object] | None = None
    vehicle: carla.Vehicle | None = None
    sensors: list[SensorRuntime] = []
    collision_sensor: carla.Sensor | None = None
    stopped_sensor_ids: set[int] = set()
    samples: list[dict[str, object]] = []
    trajectory: list[dict[str, object]] = []
    collisions: list[dict[str, object]] = []
    discarded_frames: set[int] = set()
    duplicate_keys: list[str] = []
    resource_samples = [resource_sample()]
    started_wall = time.monotonic()
    outcome = "failed_before_drive"
    route: RouteDefinition | None = None
    writer_pool = ThreadPoolExecutor(max_workers=args.writer_workers, thread_name_prefix="stage4-png")
    pending_writes: collections.deque[PendingWrite] = collections.deque()
    writer_backpressure_wall_s = 0.0
    scheduled_sample_count = 0
    try:
        available_maps = list(client.get_available_maps())
        map_name = str(config["map_name"])
        resolved_map = next((name for name in available_maps if short_map_name(name).lower() == map_name.lower()), None)
        if resolved_map is None:
            raise RuntimeError(f"{map_name} is not available")
        world = client.load_world(resolved_map, reset_settings=False, map_layers=carla.MapLayer.All)
        original_settings = configure_synchronous_world(world)
        map_ = world.get_map()
        if short_map_name(map_.name).lower() != map_name.lower():
            raise RuntimeError(f"loaded {map_.name}, expected {map_name}")
        road_line_operation = hide_road_lines(world)
        weather_record = apply_weather(world, args.weather_id, profiles[args.weather_id])
        route = load_route(map_, routes_run / str(route_item["path"]), map_name, float(index["dense_step_m"]))
        traffic_manager = client.get_trafficmanager(args.traffic_manager_port)
        traffic_manager.set_synchronous_mode(True)
        traffic_manager.set_random_device_seed(int(config["traffic_manager_seed"]))
        blueprint = choose_vehicle_blueprint(world.get_blueprint_library())
        vehicle = spawn_at_route_start(world, blueprint, route)
        spawn_frame = world.tick()
        if world.get_snapshot().find(vehicle.id) is None:
            raise RuntimeError(f"vehicle absent after spawn frame {spawn_frame}")
        events: queue.Queue[tuple[str, carla.Image]] = queue.Queue()
        sensors, calibration_record = calibration_and_sensors(
            world, vehicle, calibration_path, calibration, float(config["mount_z_offset_m"]), float(config["sensor_tick_seconds"]), events
        )
        write_json(run_dir / "calibration.json", calibration_record)
        collision_sensor = world.spawn_actor(world.get_blueprint_library().find("sensor.other.collision"), carla.Transform(), attach_to=vehicle)
        if not isinstance(collision_sensor, carla.Sensor):
            raise RuntimeError("collision actor is not a sensor")
        collision_sensor.listen(lambda event: collisions.append(collision_record(event)))
        runtimes = {sensor.key: sensor for sensor in sensors}
        expected_keys = set(runtimes)
        if len(expected_keys) != 18:
            raise RuntimeError("baseline rig did not create 18 unique sensor streams")
        traffic_manager.auto_lane_change(vehicle, False)
        traffic_manager.ignore_lights_percentage(vehicle, 100.0)
        traffic_manager.ignore_signs_percentage(vehicle, 100.0)
        traffic_manager.vehicle_percentage_speed_difference(vehicle, -20.0)
        vehicle.set_autopilot(True, args.traffic_manager_port)
        traffic_manager.set_route(vehicle, route.traffic_manager_route_instructions)
        write_json(run_dir / "scene.json", {"map_name": map_.name, "weather": weather_record, "road_line_operation": road_line_operation, "debug_drawings": "none"})
        recording_scope = "Stage-4 throughput benchmark" if args.benchmark_simulation_s else "complete Stage-4 baseline drive"
        write_json(run_dir / "route.json", {"route_id": route.route_id, "source": route.source_path.as_posix(), "length_m": route.length_m, "traffic_manager_route_instructions": route.traffic_manager_route_instructions, "recording_scope": recording_scope})
        write_json(run_dir / "baseline_config.json", {"matrix_config": config, "route_id": args.route_id, "weather_id": args.weather_id, "free_disk_gib_before_run": available_before_gib, "writer": {"workers": args.writer_workers, "max_pending_write_samples": args.max_pending_write_samples, "resource_sample_every": args.resource_sample_every}, "benchmark_simulation_s": args.benchmark_simulation_s})

        initial_snapshot = world.get_snapshot()
        start_simulation_s = float(initial_snapshot.timestamp.elapsed_seconds)
        warmup_end_s = start_simulation_s + float(config["warmup_seconds"])
        maximum_end_s = start_simulation_s + max(float(config["route_timeout_seconds"]), args.benchmark_simulation_s)
        pending: dict[int, dict[str, carla.Image]] = {}
        first_event_wall: dict[int, float] = {}
        poses: dict[int, dict[str, object]] = {}
        route_states: dict[int, dict[str, object]] = {}
        history: collections.deque[dict[str, object]] = collections.deque()
        maximum_deviation_m = 0.0
        maximum_progress_m = 0.0
        completion_record: dict[str, object] | None = None
        stuck_diagnostic: dict[str, object] | None = None
        last_scheduled_timestamp_s: float | None = None
        partial_path = run_dir / "transforms.partial.json"
        while True:
            tick_frame = world.tick()
            snapshot = world.get_snapshot()
            if int(snapshot.frame) != int(tick_frame):
                raise RuntimeError("world snapshot frame differs from synchronous tick")
            frame = int(snapshot.frame)
            pose = pose_from_snapshot(snapshot, vehicle.id)
            poses[frame] = pose
            state = route_state(snapshot, vehicle.id, route)
            route_states[frame] = state
            trajectory.append({**pose, "route_state": state})
            maximum_deviation_m = max(maximum_deviation_m, float(state["nearest_route_distance_m"]))
            if float(state["nearest_route_distance_m"]) <= float(config["path_deviation_limit_m"]):
                maximum_progress_m = max(maximum_progress_m, float(state["nearest_route_progress_m"]))
            history.append({**state, "speed_mps": float(pose["speed_mps"]), "transform": pose["transform"]})
            while len(history) > 1 and float(state["simulation_time_s"]) - float(history[0]["simulation_time_s"]) > float(config["stuck_window_seconds"]):
                history.popleft()
            drain_sensor_events(events, pending, first_event_wall, duplicate_keys, expected_keys, args.sensor_timeout_s)
            for complete_frame in sorted(list(pending)):
                images = pending.pop(complete_frame)
                first_event_wall.pop(complete_frame, None)
                if complete_frame not in poses:
                    raise RuntimeError(f"sensor frame {complete_frame} lacks a same-frame ego pose")
                if complete_frame not in route_states:
                    raise RuntimeError(f"sensor frame {complete_frame} lacks a same-frame route state")
                timestamps = [float(image.timestamp) for image in images.values()]
                if max(timestamps) - min(timestamps) > 1e-6:
                    raise RuntimeError(f"sensor timestamps differ within frame {complete_frame}")
                if abs(timestamps[0] - float(poses[complete_frame]["simulation_time_s"])) > 1e-4:
                    raise RuntimeError(f"sensor and ego timestamps differ at frame {complete_frame}")
                if timestamps[0] + 1e-9 < warmup_end_s:
                    discarded_frames.add(complete_frame)
                    continue
                if last_scheduled_timestamp_s is not None and abs(timestamps[0] - last_scheduled_timestamp_s - float(config["sensor_tick_seconds"])) > 1e-4:
                    raise RuntimeError("accepted capture interval differs from configured 0.5 s")
                sample_index = scheduled_sample_count
                pose_for_sample = {**poses[complete_frame], "route_state": route_states[complete_frame]}
                prepared = prepare_sample_buffers(images, runtimes)
                pending_writes.append(
                    PendingWrite(
                        sample_index=sample_index,
                        future=writer_pool.submit(
                            save_prepared_sample,
                            run_dir,
                            sample_index,
                            complete_frame,
                            timestamps[0],
                            prepared,
                            pose_for_sample,
                        ),
                    )
                )
                scheduled_sample_count += 1
                last_scheduled_timestamp_s = timestamps[0]
                if scheduled_sample_count % args.resource_sample_every == 0:
                    resource_samples.append(resource_sample())
                while len(pending_writes) >= args.max_pending_write_samples:
                    writer_backpressure_wall_s += finish_one_write(pending_writes, samples, partial_path)
            poses = {key: value for key, value in poses.items() if key >= frame - 40}
            route_states = {key: value for key, value in route_states.items() if key >= frame - 40}
            elapsed_s = float(state["simulation_time_s"]) - start_simulation_s
            if collisions:
                outcome = "collision"
                break
            if args.benchmark_simulation_s and elapsed_s >= args.benchmark_simulation_s:
                outcome = "benchmark_duration_reached"
                break
            if not args.benchmark_simulation_s and float(state["distance_to_finish_m"]) <= float(config["finish_radius_m"]) and maximum_progress_m >= route.length_m * 0.95:
                outcome = "completed"
                completion_record = {**state, "speed_mps": float(pose["speed_mps"]), "transform": pose["transform"]}
                break
            if not args.benchmark_simulation_s and elapsed_s >= float(config["route_timeout_seconds"]):
                outcome = "timeout"
                break
            if not args.benchmark_simulation_s and elapsed_s >= float(config["stuck_grace_seconds"]) and len(history) > 1:
                oldest = history[0]
                moved_m = distance_2d(location_from_dict(oldest["transform"]["location"]), location_from_dict(pose["transform"]["location"]))
                progress_gain_m = float(state["nearest_route_progress_m"]) - float(oldest["nearest_route_progress_m"])
                if moved_m < 1.0 and progress_gain_m < 0.5 and max(float(item["speed_mps"]) for item in history) < 0.5:
                    outcome = "stuck"
                    stuck_diagnostic = {"moved_m": moved_m, "progress_gain_m": progress_gain_m, "window_s": elapsed_s}
                    break
            if float(state["simulation_time_s"]) > maximum_end_s:
                outcome = "timeout"
                break

        vehicle.set_autopilot(False, args.traffic_manager_port)
        post_finish = stop_after_completion(world, vehicle, float(config["fixed_delta_seconds"]), duration_s=1.0)
        write_json(run_dir / "trajectory.json", trajectory)
        write_json(run_dir / "collisions.json", collisions)
        drive_result = {
            "route_id": route.route_id,
            "weather_id": args.weather_id,
            "outcome": outcome,
            "completion_record": completion_record,
            "collision_count": len(collisions),
            "maximum_deviation_m": maximum_deviation_m,
            "maximum_progress_m": maximum_progress_m,
            "required_completion_progress_m": route.length_m * 0.95,
            "route_length_m": route.length_m,
            "post_finish_stop": post_finish,
            "stuck_diagnostic": stuck_diagnostic,
        }
        write_json(run_dir / "drive_result.json", drive_result)
        accepted_outcomes = {"benchmark_duration_reached"} if args.benchmark_simulation_s else {"completed"}
        if outcome not in accepted_outcomes:
            raise RuntimeError(f"recording ended {outcome}")
        for sensor in sensors:
            sensor.actor.stop()
            stopped_sensor_ids.add(int(sensor.actor.id))
        late_events = 0
        while True:
            try:
                events.get(timeout=0.1)
                late_events += 1
            except queue.Empty:
                break
        while pending_writes:
            writer_backpressure_wall_s += finish_one_write(pending_writes, samples, partial_path)
        final_document = {"schema_version": 1, "state": "complete", "coordinate_system": "CARLA world coordinates in metres; rotations in degrees", "recording_frequency_hz": 1.0 / float(config["sensor_tick_seconds"]), "fixed_delta_seconds": float(config["fixed_delta_seconds"]), "samples": samples}
        write_json(run_dir / "transforms.json", final_document)
        if partial_path.exists():
            partial_path.unlink()
        span_s = float(samples[-1]["sensor_timestamp_s"]) - float(samples[0]["sensor_timestamp_s"]) if len(samples) > 1 else 0.0
        resource_samples.append(resource_sample())
        summary = {"selected_camera_names": list(CAMERA_ORDER), "sensor_count": len(sensors), "sample_count": len(samples), "image_count": len(samples) * len(sensors), "preview_count": len(samples) * len(CAMERA_ORDER), "warmup_discarded_complete_frames": sorted(discarded_frames), "duplicate_sensor_keys": duplicate_keys, "late_events_drained_after_stop": late_events, "wall_duration_s": time.monotonic() - started_wall, "accepted_capture_span_simulation_s": span_s, "bytes_at_summary_time": directory_bytes(run_dir), "bytes_per_accepted_simulation_second": (directory_bytes(run_dir) / span_s if span_s else None), "writer": {"workers": args.writer_workers, "max_pending_write_samples": args.max_pending_write_samples, "scheduled_sample_count": scheduled_sample_count, "backpressure_wall_s": writer_backpressure_wall_s}, "benchmark_simulation_s": args.benchmark_simulation_s or None, "resource_samples": resource_samples}
        write_json(run_dir / "capture_summary.json", summary)
        validator = Path(__file__).with_name("stage3_validate_dataset.py")
        subprocess.run([sys.executable, str(validator), str(run_dir), "--require-all-nine"], check=True)
        dataset_validation = load_json(run_dir / "validation.json")
        validation_name = "benchmark_validation.json" if args.benchmark_simulation_s else "baseline_validation.json"
        validation_checks: dict[str, object] = {
            "expected_recording_outcome": outcome in accepted_outcomes,
            "no_collision": not collisions,
            "post_finish_vehicle_stopped": bool(post_finish["stopped"]),
            "all_dataset_checks_passed": dataset_validation["status"] == "passed",
        }
        if not args.benchmark_simulation_s:
            validation_checks["route_deviation_within_limit"] = maximum_deviation_m <= float(config["path_deviation_limit_m"])
        recording_validation = {"status": "passed" if dataset_validation["status"] == "passed" and outcome in accepted_outcomes else "failed", "dataset_validation_path": "validation.json", "drive_result_path": "drive_result.json", "checks": validation_checks}
        write_json(run_dir / validation_name, recording_validation)
        update_metadata(metadata_path, state="running", carla_client_version=client.get_client_version(), carla_server_version=client.get_server_version(), map_name=map_.name, route_id=args.route_id, weather_id=args.weather_id, validation_path=validation_name, validation_status=recording_validation["status"])
        if recording_validation["status"] != "passed":
            raise RuntimeError("recording validation failed")
        print(run_dir / validation_name)
    except Exception as exc:
        update_metadata(metadata_path, state="failed", stage4_recording_error=str(exc), route_id=args.route_id, weather_id=args.weather_id)
        raise
    finally:
        writer_pool.shutdown(wait=True, cancel_futures=False)
        if collision_sensor is not None:
            try:
                collision_sensor.stop()
                collision_sensor.destroy()
            except RuntimeError:
                pass
        for sensor in reversed(sensors):
            try:
                if int(sensor.actor.id) not in stopped_sensor_ids:
                    sensor.actor.stop()
                sensor.actor.destroy()
            except RuntimeError:
                pass
        if vehicle is not None:
            try:
                vehicle.set_autopilot(False, args.traffic_manager_port)
                vehicle.destroy()
            except RuntimeError:
                pass
        if traffic_manager is not None:
            try:
                traffic_manager.set_synchronous_mode(False)
            except RuntimeError:
                pass
        if world is not None and original_settings is not None:
            try:
                restore_world_settings(world, original_settings)
            except RuntimeError:
                pass


if __name__ == "__main__":
    main()
