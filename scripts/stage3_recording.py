#!/usr/bin/env python3
"""Record a short synchronous drive with the nine-position AV2 camera rig."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import queue
import struct
import subprocess
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import carla

from stage2_autopilot_routes import choose_vehicle_blueprint, load_route, spawn_at_route_start
from stage2_routes import (
    configure_synchronous_world,
    hide_road_lines,
    restore_world_settings,
    short_map_name,
    transform_to_dict,
    update_metadata,
    write_json,
)
from stage3_geometry import (
    av2_camera_to_carla_actor_matrix,
    av2_translation_to_carla,
    carla_euler_to_matrix,
    horizontal_fov_deg,
    homogeneous_transform_point,
    matrix_determinant,
    matrix_to_carla_euler_deg,
    max_identity_error,
    point_inside_box,
    quaternion_to_matrix,
    ray_intersects_box,
    rear_axle_midpoint_m,
)


CAMERA_ORDER = (
    "ring_front_center",
    "ring_front_left",
    "ring_front_right",
    "ring_side_left",
    "ring_side_right",
    "ring_rear_left",
    "ring_rear_right",
    "stereo_front_left",
    "stereo_front_right",
)
MODALITIES = ("rgb", "semantic")


@dataclass
class SensorRuntime:
    key: str
    camera_name: str
    modality: str
    actor: carla.Sensor
    width: int
    height: int


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def write_grayscale_png(path: Path, width: int, height: int, pixels: bytes) -> None:
    """Write unmodified 8-bit class IDs without an image-library dependency."""
    if len(pixels) != width * height:
        raise ValueError(f"raw semantic buffer has {len(pixels)} bytes, expected {width * height}")
    scanlines = b"".join(b"\x00" + pixels[row * width : (row + 1) * width] for row in range(height))
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(scanlines, level=6))
        + png_chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def matrix_max_difference(first: list[list[float]], second: list[list[float]]) -> float:
    return max(abs(first[row][column] - second[row][column]) for row in range(3) for column in range(3))


def vector_to_list(value: carla.Vector3D) -> list[float]:
    return [float(value.x), float(value.y), float(value.z)]


def speed_mps_from_snapshot(actor_snapshot: carla.ActorSnapshot) -> float:
    velocity = actor_snapshot.get_velocity()
    return math.sqrt(float(velocity.x) ** 2 + float(velocity.y) ** 2 + float(velocity.z) ** 2)


def pose_from_snapshot(snapshot: carla.WorldSnapshot, vehicle_id: int) -> dict[str, object]:
    actor_snapshot = snapshot.find(vehicle_id)
    if actor_snapshot is None:
        raise RuntimeError(f"vehicle {vehicle_id} is absent from world snapshot {snapshot.frame}")
    return {
        "frame": int(snapshot.frame),
        "simulation_time_s": float(snapshot.timestamp.elapsed_seconds),
        "transform": transform_to_dict(actor_snapshot.get_transform()),
        "velocity_mps": vector_to_list(actor_snapshot.get_velocity()),
        "angular_velocity_deg_s": vector_to_list(actor_snapshot.get_angular_velocity()),
        "speed_mps": speed_mps_from_snapshot(actor_snapshot),
        "coordinate_system": "CARLA world: metres; x/y/z and roll/pitch/yaw in degrees",
    }


def resource_sample() -> dict[str, object]:
    result: dict[str, object] = {"wall_monotonic_s": time.monotonic()}
    try:
        fields: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            name, value = line.split(":", 1)
            if name in {"MemTotal", "MemAvailable"}:
                fields[name] = int(value.strip().split()[0]) * 1024
        result["host_memory_total_bytes"] = fields.get("MemTotal")
        result["host_memory_used_bytes"] = fields.get("MemTotal", 0) - fields.get("MemAvailable", 0)
    except (OSError, ValueError):
        result["host_memory_error"] = "could not parse /proc/meminfo"
    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=5,
        ).strip().splitlines()[0]
        used, total, utilisation = (int(value.strip()) for value in output.split(","))
        result.update(
            gpu_memory_used_mib=used,
            gpu_memory_total_mib=total,
            gpu_utilization_percent=utilisation,
        )
    except (OSError, subprocess.SubprocessError, ValueError, IndexError) as exc:
        result["gpu_query_error"] = str(exc)
    return result


def directory_bytes(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def verify_source_files(calibration_path: Path, document: dict[str, Any]) -> None:
    for relative, expected in document["source"]["files"].items():
        path = calibration_path.parent / relative
        if not path.is_file():
            raise RuntimeError(f"missing raw AV2 calibration source: {path}")
        actual = file_sha256(path)
        if actual != expected:
            raise RuntimeError(f"AV2 calibration source hash mismatch: {path}")


def applied_camera_configuration(
    camera: dict[str, Any],
    rear_axle_origin_m: tuple[float, float, float],
    mount_z_offset_m: float,
    bbox_centre: tuple[float, float, float],
    bbox_extent: tuple[float, float, float],
) -> tuple[carla.Transform, dict[str, object]]:
    extrinsic = camera["egovehicle_SE3_sensor"]
    av2_rotation = quaternion_to_matrix(*(float(extrinsic[key]) for key in ("qw", "qx", "qy", "qz")))
    actor_matrix = av2_camera_to_carla_actor_matrix(av2_rotation)
    euler = matrix_to_carla_euler_deg(actor_matrix)
    rebuilt = carla_euler_to_matrix(**euler)
    location = list(
        av2_translation_to_carla(
            (float(extrinsic["tx_m"]), float(extrinsic["ty_m"]), float(extrinsic["tz_m"])),
            rear_axle_origin_m,
        )
    )
    location[2] += mount_z_offset_m
    transform = carla.Transform(
        carla.Location(x=location[0], y=location[1], z=location[2]),
        carla.Rotation(roll=euler["roll"], pitch=euler["pitch"], yaw=euler["yaw"]),
    )
    intrinsics = camera["intrinsics"]
    width, height = int(intrinsics["width_px"]), int(intrinsics["height_px"])
    fov = horizontal_fov_deg(width, float(intrinsics["fx_px"]))
    forward = (actor_matrix[0][0], actor_matrix[1][0], actor_matrix[2][0])
    origin_inside = point_inside_box(location, bbox_centre, bbox_extent)
    optical_axis_hits_body = ray_intersects_box(location, forward, bbox_centre, bbox_extent)
    if origin_inside:
        raise RuntimeError(f"{camera['sensor_name']} origin is inside the CARLA vehicle bounding box")
    if optical_axis_hits_body:
        raise RuntimeError(f"{camera['sensor_name']} optical axis intersects the CARLA vehicle bounding box")
    applied = {
        "sensor_name": camera["sensor_name"],
        "raw_av2": camera,
        "carla_relative_transform": transform_to_dict(transform),
        "carla_local_to_vehicle_rotation_matrix": actor_matrix,
        "carla_camera_forward_axis_in_vehicle": list(forward),
        "horizontal_fov_deg": fov,
        "image_width_px": width,
        "image_height_px": height,
        "principal_point_offset_from_image_centre_px": {
            "x": float(intrinsics["cx_px"]) - width / 2.0,
            "y": float(intrinsics["cy_px"]) - height / 2.0,
        },
        "numeric_checks": {
            "rotation_determinant": matrix_determinant(actor_matrix),
            "orthonormal_max_error": max_identity_error(actor_matrix),
            "euler_roundtrip_max_error": matrix_max_difference(actor_matrix, rebuilt),
            "origin_outside_vehicle_bbox": not origin_inside,
            "optical_axis_misses_vehicle_bbox": not optical_axis_hits_body,
        },
        "projection_limits": (
            "CARLA receives AV2 width/height and the horizontal FOV derived from fx. "
            "CARLA 0.9.16 cannot set AV2 cx/cy or the full k1/k2/k3 model; distortion is disabled."
        ),
    }
    return transform, applied


def configure_sensor_blueprint(
    library: carla.BlueprintLibrary,
    modality: str,
    applied: dict[str, Any],
    sensor_tick_s: float,
) -> carla.ActorBlueprint:
    blueprint_id = "sensor.camera.rgb" if modality == "rgb" else "sensor.camera.semantic_segmentation"
    blueprint = library.find(blueprint_id)
    attributes = {
        "image_size_x": str(applied["image_width_px"]),
        "image_size_y": str(applied["image_height_px"]),
        "fov": f"{float(applied['horizontal_fov_deg']):.12f}",
        "sensor_tick": f"{sensor_tick_s:.12f}",
        "lens_k": "0.0",
        "lens_kcube": "0.0",
    }
    if modality == "rgb" and blueprint.has_attribute("gamma"):
        attributes["gamma"] = "2.2"
    for name, value in attributes.items():
        if blueprint.has_attribute(name):
            blueprint.set_attribute(name, value)
    return blueprint


def save_sample(
    run_dir: Path,
    sample_index: int,
    frame: int,
    images: dict[str, carla.Image],
    runtimes: dict[str, SensorRuntime],
    pose: dict[str, object],
) -> dict[str, object]:
    files: dict[str, dict[str, str]] = {}
    semantic_ids: dict[str, list[int]] = {}
    stem = f"{sample_index:06d}_{frame:08d}.png"
    for camera_name in CAMERA_ORDER:
        rgb_key, semantic_key = f"rgb:{camera_name}", f"semantic:{camera_name}"
        if rgb_key not in runtimes:
            continue
        rgb_path = run_dir / "rgb" / camera_name / stem
        semantic_path = run_dir / "semantic" / camera_name / stem
        preview_path = run_dir / "previews" / "semantic" / camera_name / stem
        rgb_path.parent.mkdir(parents=True, exist_ok=True)
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        rgb_image, semantic_image = images[rgb_key], images[semantic_key]
        rgb_image.save_to_disk(str(rgb_path), carla.ColorConverter.Raw)
        class_ids = bytes(memoryview(semantic_image.raw_data)[2::4])
        write_grayscale_png(semantic_path, semantic_image.width, semantic_image.height, class_ids)
        semantic_image.save_to_disk(str(preview_path), carla.ColorConverter.CityScapesPalette)
        for path in (rgb_path, semantic_path, preview_path):
            if not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError(f"sensor output was not written: {path}")
        files[camera_name] = {
            "rgb": rgb_path.relative_to(run_dir).as_posix(),
            "semantic_raw_ids": semantic_path.relative_to(run_dir).as_posix(),
            "semantic_preview": preview_path.relative_to(run_dir).as_posix(),
        }
        semantic_ids[camera_name] = sorted(set(class_ids))
    return {
        **pose,
        "sample_index": sample_index,
        "sensor_timestamp_s": float(next(iter(images.values())).timestamp),
        "images": files,
        "semantic_class_ids_present": semantic_ids,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument(
        "--calibration",
        type=Path,
        default=Path("configs/av2/54bc6dbc-ebfb-3fba-b5b3-57f88b4b79ca/calibration.json"),
    )
    parser.add_argument(
        "--routes-run", type=Path, default=Path("runs/20260919T154916Z-route-numbering-swap-b5e941")
    )
    parser.add_argument("--route-id", default="route_01_straight")
    parser.add_argument("--camera-name", action="append", default=[])
    parser.add_argument("--sample-count", type=int, default=6)
    parser.add_argument("--warmup-s", type=float, default=1.0)
    parser.add_argument("--fixed-delta-s", type=float, default=0.05)
    parser.add_argument("--sensor-tick-s", type=float, default=0.5)
    parser.add_argument("--sensor-timeout-s", type=float, default=30.0)
    parser.add_argument("--maximum-simulation-s", type=float, default=20.0)
    parser.add_argument("--mount-z-offset-m", type=float, default=0.0)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--traffic-manager-port", type=int, default=8000)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--map-name", default="Town01_Opt")
    args = parser.parse_args()
    if args.sample_count <= 0 or args.sensor_tick_s <= 0.0 or args.fixed_delta_s <= 0.0:
        raise SystemExit("sample count and timing values must be positive")
    ratio = args.sensor_tick_s / args.fixed_delta_s
    if abs(ratio - round(ratio)) > 1e-9:
        raise SystemExit("sensor tick must be an integer multiple of fixed delta")

    run_dir = args.run_dir.resolve()
    metadata_path = run_dir / "metadata.json"
    calibration_path = args.calibration.resolve()
    routes_run = args.routes_run.resolve()
    if not metadata_path.is_file():
        raise SystemExit(f"run directory was not created by create_run.py: {run_dir}")
    source_calibration = json.loads(calibration_path.read_text())
    verify_source_files(calibration_path, source_calibration)
    by_name = {camera["sensor_name"]: camera for camera in source_calibration["cameras"]}
    selected_names = args.camera_name or list(CAMERA_ORDER)
    if len(selected_names) != len(set(selected_names)) or any(name not in by_name for name in selected_names):
        raise SystemExit("camera selection contains duplicates or unknown names")
    selected_names = [name for name in CAMERA_ORDER if name in selected_names]

    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout)
    world: carla.World | None = None
    traffic_manager: carla.TrafficManager | None = None
    original_settings: dict[str, object] | None = None
    vehicle: carla.Vehicle | None = None
    sensors: list[SensorRuntime] = []
    stopped_sensor_ids: set[int] = set()
    started_wall = time.monotonic()
    resource_samples = [resource_sample()]
    samples: list[dict[str, object]] = []
    discarded_frames: set[int] = set()
    duplicate_keys: list[str] = []
    late_events_after_stop = 0
    try:
        available_maps = list(client.get_available_maps())
        resolved_map = next(
            (name for name in available_maps if short_map_name(name).lower() == args.map_name.lower()), None
        )
        if resolved_map is None:
            raise RuntimeError(f"{args.map_name} is not available")
        world = client.load_world(resolved_map, reset_settings=False, map_layers=carla.MapLayer.All)
        original_settings = configure_synchronous_world(world)
        map_ = world.get_map()
        road_line_operation = hide_road_lines(world)
        traffic_manager = client.get_trafficmanager(args.traffic_manager_port)
        traffic_manager.set_synchronous_mode(True)
        traffic_manager.set_random_device_seed(2026091906)

        index = json.loads((routes_run / "revised_routes.json").read_text())
        route_item = next((item for item in index["routes"] if item["route_id"] == args.route_id), None)
        if route_item is None:
            raise RuntimeError(f"unknown approved route: {args.route_id}")
        route = load_route(map_, routes_run / route_item["path"], args.map_name, float(index["dense_step_m"]))
        blueprint = choose_vehicle_blueprint(world.get_blueprint_library())
        vehicle = spawn_at_route_start(world, blueprint, route)
        # A newly spawned actor reports an identity transform and world-space
        # wheel positions until the synchronous world advances once.
        spawn_frame = world.tick()
        if world.get_snapshot().find(vehicle.id) is None:
            raise RuntimeError(f"vehicle is absent after spawn frame {spawn_frame}")
        physics = vehicle.get_physics_control()
        wheel_positions_world_cm = [
            [wheel.position.x, wheel.position.y, wheel.position.z] for wheel in physics.wheels
        ]
        inverse_vehicle_matrix = vehicle.get_transform().get_inverse_matrix()
        wheel_positions_local_m = [
            homogeneous_transform_point(
                inverse_vehicle_matrix,
                (position[0] / 100.0, position[1] / 100.0, position[2] / 100.0),
            )
            for position in wheel_positions_world_cm
        ]
        rear_axle_origin, wheel_positions_m = rear_axle_midpoint_m(
            [[component * 100.0 for component in position] for position in wheel_positions_local_m]
        )
        bbox_centre = tuple(float(value) for value in (vehicle.bounding_box.location.x, vehicle.bounding_box.location.y, vehicle.bounding_box.location.z))
        bbox_extent = tuple(float(value) for value in (vehicle.bounding_box.extent.x, vehicle.bounding_box.extent.y, vehicle.bounding_box.extent.z))

        applied_cameras: list[dict[str, object]] = []
        transforms: dict[str, carla.Transform] = {}
        for name in selected_names:
            transform, applied = applied_camera_configuration(
                by_name[name], rear_axle_origin, args.mount_z_offset_m, bbox_centre, bbox_extent
            )
            transforms[name] = transform
            applied_cameras.append(applied)
        calibration_record = {
            "schema_version": 1,
            "source_calibration_path": calibration_path.relative_to(Path.cwd()).as_posix(),
            "source": source_calibration["source"],
            "log_id": source_calibration["log_id"],
            "coordinate_conversion": {
                "av2_ego_to_carla_vehicle": "(x,y,z) -> (x,-y,z)",
                "av2_optical_to_carla_camera": "(x_right,y_down,z_forward) -> (y_right,-z_up,x_forward)",
                "av2_ego_origin": "rear axle centre",
                "carla_rear_axle_origin_relative_to_actor_m": list(rear_axle_origin),
                "mount_z_offset_m": args.mount_z_offset_m,
                "wheel_positions_reported_by_carla_world_cm": wheel_positions_world_cm,
                "wheel_positions_relative_to_actor_m": [list(value) for value in wheel_positions_m],
            },
            "carla_vehicle": {
                "blueprint": blueprint.id,
                "semantic_tags_reported_by_actor": [int(tag) for tag in vehicle.semantic_tags],
                "bounding_box_centre_m": list(bbox_centre),
                "bounding_box_extent_m": list(bbox_extent),
            },
            "applied_cameras": applied_cameras,
        }
        write_json(run_dir / "calibration.json", calibration_record)
        write_json(
            run_dir / "scene.json",
            {
                "map_name": map_.name,
                "weather": str(world.get_weather()),
                "road_line_operation": road_line_operation,
                "debug_drawings": "none",
            },
        )
        write_json(
            run_dir / "route.json",
            {
                "route_id": route.route_id,
                "source": route.source_path.as_posix(),
                "length_m": route.length_m,
                "traffic_manager_route_instructions": route.traffic_manager_route_instructions,
                "recording_scope": "short Stage-3 rig validation, not a complete Stage-4 route drive",
            },
        )

        events: queue.Queue[tuple[str, carla.Image]] = queue.Queue()
        library = world.get_blueprint_library()
        applied_by_name = {item["sensor_name"]: item for item in applied_cameras}
        for camera_name in selected_names:
            for modality in MODALITIES:
                applied = applied_by_name[camera_name]
                sensor_blueprint = configure_sensor_blueprint(library, modality, applied, args.sensor_tick_s)
                actor = world.spawn_actor(
                    sensor_blueprint,
                    transforms[camera_name],
                    attach_to=vehicle,
                    attachment_type=carla.AttachmentType.Rigid,
                )
                if not isinstance(actor, carla.Sensor):
                    raise RuntimeError(f"spawned actor is not a sensor: {modality}:{camera_name}")
                key = f"{modality}:{camera_name}"
                runtime = SensorRuntime(
                    key=key,
                    camera_name=camera_name,
                    modality=modality,
                    actor=actor,
                    width=int(applied["image_width_px"]),
                    height=int(applied["image_height_px"]),
                )
                sensors.append(runtime)
                actor.listen(lambda image, sensor_key=key: events.put((sensor_key, image)))
        runtimes = {sensor.key: sensor for sensor in sensors}
        expected_keys = set(runtimes)
        if len(expected_keys) != len(selected_names) * 2:
            raise RuntimeError("sensor key count does not match two modalities per camera")

        traffic_manager.auto_lane_change(vehicle, False)
        traffic_manager.ignore_lights_percentage(vehicle, 100.0)
        traffic_manager.ignore_signs_percentage(vehicle, 100.0)
        traffic_manager.vehicle_percentage_speed_difference(vehicle, -20.0)
        vehicle.set_autopilot(True, args.traffic_manager_port)
        traffic_manager.set_route(vehicle, route.traffic_manager_route_instructions)

        initial_snapshot = world.get_snapshot()
        initial_time = float(initial_snapshot.timestamp.elapsed_seconds)
        warmup_end = initial_time + args.warmup_s
        maximum_end = warmup_end + args.maximum_simulation_s
        pending: dict[int, dict[str, carla.Image]] = {}
        first_event_wall: dict[int, float] = {}
        poses: dict[int, dict[str, object]] = {}

        while len(samples) < args.sample_count:
            tick_frame = world.tick()
            snapshot = world.get_snapshot()
            if int(snapshot.frame) != int(tick_frame):
                raise RuntimeError("world snapshot frame differs from synchronous tick frame")
            frame = int(snapshot.frame)
            poses[frame] = pose_from_snapshot(snapshot, vehicle.id)
            simulation_time = float(snapshot.timestamp.elapsed_seconds)
            if simulation_time > maximum_end:
                raise TimeoutError(f"collected {len(samples)}/{args.sample_count} samples before simulation timeout")

            try:
                key, image = events.get(timeout=0.05)
                batch = [(key, image)]
            except queue.Empty:
                batch = []
            while True:
                try:
                    batch.append(events.get_nowait())
                except queue.Empty:
                    break
            for key, image in batch:
                image_frame = int(image.frame)
                frame_images = pending.setdefault(image_frame, {})
                if key in frame_images:
                    duplicate_keys.append(f"{image_frame}:{key}")
                frame_images[key] = image
                first_event_wall.setdefault(image_frame, time.monotonic())

            incomplete = [item for item in pending if set(pending[item]) != expected_keys]
            while incomplete:
                oldest = min(incomplete, key=first_event_wall.__getitem__)
                remaining = args.sensor_timeout_s - (time.monotonic() - first_event_wall[oldest])
                if remaining <= 0.0:
                    missing = sorted(expected_keys - set(pending[oldest]))
                    raise TimeoutError(f"sensor frame {oldest} missed {missing}")
                try:
                    key, image = events.get(timeout=min(remaining, 0.5))
                except queue.Empty:
                    incomplete = [item for item in pending if set(pending[item]) != expected_keys]
                    continue
                image_frame = int(image.frame)
                frame_images = pending.setdefault(image_frame, {})
                if key in frame_images:
                    duplicate_keys.append(f"{image_frame}:{key}")
                frame_images[key] = image
                first_event_wall.setdefault(image_frame, time.monotonic())
                incomplete = [item for item in pending if set(pending[item]) != expected_keys]

            for complete_frame in sorted(list(pending)):
                frame_images = pending.pop(complete_frame)
                first_event_wall.pop(complete_frame, None)
                if complete_frame not in poses:
                    raise RuntimeError(f"no same-frame ego snapshot for sensor frame {complete_frame}")
                timestamps = [float(image.timestamp) for image in frame_images.values()]
                if max(timestamps) - min(timestamps) > 1e-6:
                    raise RuntimeError(f"sensor timestamps differ within frame {complete_frame}")
                pose_time = float(poses[complete_frame]["simulation_time_s"])
                if abs(timestamps[0] - pose_time) > 1e-4:
                    raise RuntimeError(f"sensor and pose timestamps differ at frame {complete_frame}")
                if timestamps[0] + 1e-9 < warmup_end:
                    discarded_frames.add(complete_frame)
                    continue
                if samples and abs(timestamps[0] - float(samples[-1]["sensor_timestamp_s"]) - args.sensor_tick_s) > 1e-4:
                    raise RuntimeError(f"non-{args.sensor_tick_s}s capture interval at frame {complete_frame}")
                sample = save_sample(
                    run_dir, len(samples), complete_frame, frame_images, runtimes, poses[complete_frame]
                )
                samples.append(sample)
                write_json(
                    run_dir / "transforms.partial.json",
                    {
                        "schema_version": 1,
                        "state": "recording",
                        "expected_sample_count": args.sample_count,
                        "samples": samples,
                    },
                )
                resource_samples.append(resource_sample())
                if len(samples) >= args.sample_count:
                    break
            minimum_retained_frame = frame - int(math.ceil(args.sensor_tick_s / args.fixed_delta_s)) * 3
            poses = {key: value for key, value in poses.items() if key >= minimum_retained_frame}

        for runtime in sensors:
            runtime.actor.stop()
            stopped_sensor_ids.add(int(runtime.actor.id))
        drain_deadline = time.monotonic() + 2.0
        while time.monotonic() < drain_deadline:
            try:
                events.get(timeout=0.1)
                late_events_after_stop += 1
            except queue.Empty:
                break
        vehicle.set_autopilot(False, args.traffic_manager_port)
        final_document = {
            "schema_version": 1,
            "state": "complete",
            "coordinate_system": "CARLA world coordinates in metres; rotations in degrees",
            "recording_frequency_hz": 1.0 / args.sensor_tick_s,
            "fixed_delta_seconds": args.fixed_delta_s,
            "samples": samples,
        }
        write_json(run_dir / "transforms.json", final_document)
        partial = run_dir / "transforms.partial.json"
        if partial.exists():
            partial.unlink()
        wall_duration = time.monotonic() - started_wall
        simulated_duration = (
            float(samples[-1]["sensor_timestamp_s"]) - float(samples[0]["sensor_timestamp_s"])
            if len(samples) > 1
            else 0.0
        )
        bytes_written = directory_bytes(run_dir)
        capture_summary = {
            "selected_camera_names": selected_names,
            "sensor_count": len(sensors),
            "sample_count": len(samples),
            "image_count": len(samples) * len(sensors),
            "preview_count": len(samples) * len(selected_names),
            "warmup_discarded_complete_frames": sorted(discarded_frames),
            "duplicate_sensor_keys": duplicate_keys,
            "late_events_drained_after_stop": late_events_after_stop,
            "wall_duration_s": wall_duration,
            "accepted_capture_span_simulation_s": simulated_duration,
            "bytes_at_summary_time": bytes_written,
            "bytes_per_accepted_simulation_second": (
                bytes_written / simulated_duration if simulated_duration > 0.0 else None
            ),
            "resource_samples": resource_samples,
        }
        write_json(run_dir / "capture_summary.json", capture_summary)
        update_metadata(
            metadata_path,
            state="running",
            carla_client_version=client.get_client_version(),
            carla_server_version=client.get_server_version(),
            map_name=map_.name,
            av2_log_id=source_calibration["log_id"],
            selected_camera_names=selected_names,
            sensor_count=len(sensors),
            sample_count=len(samples),
            transforms_path="transforms.json",
            calibration_path="calibration.json",
            capture_summary_path="capture_summary.json",
        )
        print(run_dir / "transforms.json")
    except Exception as exc:
        if samples:
            write_json(
                run_dir / "transforms.partial.json",
                {
                    "schema_version": 1,
                    "state": "interrupted",
                    "expected_sample_count": args.sample_count,
                    "samples": samples,
                    "error": str(exc),
                },
            )
        update_metadata(metadata_path, state="failed", stage3_recording_error=str(exc))
        raise
    finally:
        for runtime in reversed(sensors):
            try:
                if int(runtime.actor.id) not in stopped_sensor_ids:
                    runtime.actor.stop()
                runtime.actor.destroy()
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
