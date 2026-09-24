#!/usr/bin/env python3
"""Run the minimal AnimaSim deer validation on one AV2 front camera pair.

The script validates the prebuilt actor itself or applies one separately
validated passive Stage-7 SceneSpec. It does not create a full 18-camera
dataset and never executes model code. All animal positions are route-relative.
"""
from __future__ import annotations

import argparse
import json
import math
import queue
import time
from pathlib import Path
from typing import Any, Callable

import carla

from stage2_autopilot_routes import collision_record, load_route, spawn_at_route_start
from stage2_routes import (
    configure_synchronous_world,
    hide_road_lines,
    restore_world_settings,
    short_map_name,
    transform_to_dict,
    update_metadata,
    write_json,
)
from stage3_geometry import homogeneous_transform_point, rear_axle_midpoint_m
from stage3_recording import (
    SensorRuntime,
    applied_camera_configuration,
    configure_sensor_blueprint,
    pose_from_snapshot,
    verify_source_files,
    write_grayscale_png,
)
from stage4_baseline import apply_weather, cityscapes_preview, rgb_from_carla_bgra, write_rgb_png
from stage7_scene_spec import (
    canonical_json_sha256,
    load_stage7_config,
    load_stage7_route,
    parse_scene_spec_json,
    resolve_scene_spec as resolve_animal_scene_spec,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_KEYS = {"rgb:ring_front_center", "semantic:ring_front_center"}


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def require_mapping(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"{name} must be an object")
    return value


def require_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"{name} must be a non-empty string")
    return value


def require_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise RuntimeError(f"{name} must be a finite number")
    return float(value)


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def route_pose(route: object, progress_m: float, lateral_offset_m: float, z_offset_m: float) -> carla.Transform:
    # RouteDefinition is intentionally structural here so this helper stays
    # independent of implementation-only dataclass details.
    locations = getattr(route, "dense_locations")
    cumulative = getattr(route, "cumulative_dense_m")
    if progress_m < 0.0 or progress_m > float(getattr(route, "length_m")):
        raise RuntimeError(f"route progress {progress_m} is outside the route")
    index = next((i for i in range(len(cumulative) - 1) if cumulative[i] <= progress_m <= cumulative[i + 1]), None)
    if index is None:
        index = len(cumulative) - 2
    first, second = locations[index], locations[index + 1]
    segment = float(cumulative[index + 1] - cumulative[index])
    if segment <= 0.0:
        raise RuntimeError("route contains a zero-length segment")
    fraction = (progress_m - float(cumulative[index])) / segment
    dx, dy = float(second.x - first.x), float(second.y - first.y)
    forward_x, forward_y = dx / segment, dy / segment
    # CARLA map-plane left normal for a forward (x, y) route vector.
    left_x, left_y = -forward_y, forward_x
    location = carla.Location(
        x=float(first.x) + fraction * dx + lateral_offset_m * left_x,
        y=float(first.y) + fraction * dy + lateral_offset_m * left_y,
        z=float(first.z) + fraction * float(second.z - first.z) + z_offset_m,
    )
    yaw = math.degrees(math.atan2(forward_y, forward_x))
    return carla.Transform(location, carla.Rotation(yaw=yaw))


def copy_transform(transform: carla.Transform, *, yaw_deg: float | None = None) -> carla.Transform:
    return carla.Transform(
        carla.Location(x=transform.location.x, y=transform.location.y, z=transform.location.z),
        carla.Rotation(
            roll=transform.rotation.roll,
            pitch=transform.rotation.pitch,
            yaw=transform.rotation.yaw if yaw_deg is None else yaw_deg,
        ),
    )


def transform_distance_m(first: carla.Transform, second: carla.Transform) -> float:
    return math.hypot(float(first.location.x - second.location.x), float(first.location.y - second.location.y))


def collect_events(
    events: queue.Queue[tuple[str, carla.Image]],
    pending: dict[int, dict[str, carla.Image]],
    first_seen: dict[int, float],
) -> None:
    while True:
        try:
            key, image = events.get_nowait()
        except queue.Empty:
            return
        frame = int(image.frame)
        images = pending.setdefault(frame, {})
        if key in images:
            raise RuntimeError(f"duplicate sensor callback for {frame}:{key}")
        images[key] = image
        first_seen.setdefault(frame, time.monotonic())


def ready_pairs(
    pending: dict[int, dict[str, carla.Image]],
    first_seen: dict[int, float],
    snapshots: dict[int, carla.WorldSnapshot],
    timeout_s: float,
) -> tuple[int, dict[str, carla.Image], carla.WorldSnapshot] | None:
    now = time.monotonic()
    expired = [
        frame
        for frame, images in pending.items()
        if set(images) != EXPECTED_KEYS and now - first_seen[frame] > timeout_s
    ]
    if expired:
        frame = min(expired)
        raise TimeoutError(f"sensor frame {frame} missed {sorted(EXPECTED_KEYS - set(pending[frame]))}")
    for frame in sorted(list(pending)):
        images = pending[frame]
        if set(images) != EXPECTED_KEYS or frame not in snapshots:
            continue
        timestamps = [float(image.timestamp) for image in images.values()]
        snapshot = snapshots[frame]
        if max(timestamps) - min(timestamps) > 1e-6:
            raise RuntimeError(f"sensor timestamps differ within frame {frame}")
        if abs(timestamps[0] - float(snapshot.timestamp.elapsed_seconds)) > 1e-4:
            raise RuntimeError(f"sensor and snapshot time differ at frame {frame}")
        result = (frame, pending.pop(frame), snapshot)
        first_seen.pop(frame, None)
        return result
    return None


def save_pair(
    run_dir: Path,
    prefix: str,
    sample_index: int,
    frame: int,
    images: dict[str, carla.Image],
    snapshot: carla.WorldSnapshot,
    ego_id: int,
    animal_tags: set[int],
) -> dict[str, object]:
    rgb, semantic = images["rgb:ring_front_center"], images["semantic:ring_front_center"]
    if int(rgb.width) != int(semantic.width) or int(rgb.height) != int(semantic.height):
        raise RuntimeError("RGB and semantic dimensions differ")
    stem = f"{sample_index:06d}_{frame:08d}.png"
    rgb_path = run_dir / prefix / "rgb" / "ring_front_center" / stem
    raw_path = run_dir / prefix / "semantic" / "ring_front_center" / stem
    preview_path = run_dir / prefix / "previews" / "semantic" / "ring_front_center" / stem
    class_ids = bytes(memoryview(semantic.raw_data)[2::4])
    write_rgb_png(rgb_path, int(rgb.width), int(rgb.height), rgb_from_carla_bgra(rgb))
    write_grayscale_png(raw_path, int(semantic.width), int(semantic.height), class_ids)
    write_rgb_png(preview_path, int(semantic.width), int(semantic.height), cityscapes_preview(semantic))
    for path in (rgb_path, raw_path, preview_path):
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"sensor output was not written: {path}")
    pose = pose_from_snapshot(snapshot, ego_id)
    tag_counts = {str(tag): class_ids.count(tag) for tag in sorted(animal_tags)}
    return {
        "sample_index": sample_index,
        "frame": frame,
        "sensor_timestamp_s": float(rgb.timestamp),
        "ego_pose": pose,
        "files": {
            "rgb": rgb_path.relative_to(run_dir).as_posix(),
            "semantic_raw_ids": raw_path.relative_to(run_dir).as_posix(),
            "semantic_preview": preview_path.relative_to(run_dir).as_posix(),
        },
        "semantic_class_ids_present": sorted(set(class_ids)),
        "animal_semantic_tag_pixels": tag_counts,
    }


def wait_for_pair(
    world: carla.World,
    events: queue.Queue[tuple[str, carla.Image]],
    pending: dict[int, dict[str, carla.Image]],
    first_seen: dict[int, float],
    snapshots: dict[int, carla.WorldSnapshot],
    timeout_s: float,
    before_tick: Callable[[carla.WorldSnapshot], None] | None = None,
) -> tuple[int, dict[str, carla.Image], carla.WorldSnapshot]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if before_tick is not None:
            before_tick(world.get_snapshot())
        frame = int(world.tick())
        snapshot = world.get_snapshot()
        if int(snapshot.frame) != frame:
            raise RuntimeError("world snapshot frame differs from synchronous tick")
        snapshots[frame] = snapshot
        try:
            key, image = events.get(timeout=0.05)
            events.put((key, image))
        except queue.Empty:
            pass
        collect_events(events, pending, first_seen)
        pair = ready_pairs(pending, first_seen, snapshots, timeout_s)
        if pair is not None:
            return pair
        snapshots = {key: value for key, value in snapshots.items() if key >= frame - 80}
    raise TimeoutError("did not receive a complete RGB/semantic pair")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/stage7_animasim_probe.json"))
    parser.add_argument("--scene-spec", type=Path, help="Validated passive Stage-7 SceneSpec; never executable code.")
    parser.add_argument("--api-attempt-result", type=Path, help="Passed Stage-7 adapter result that owns --scene-spec.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.is_file():
        raise SystemExit(f"run directory was not created by create_run.py: {run_dir}")
    config_path = args.config.resolve()
    config = load_object(config_path)
    if config.get("schema_version") != 1:
        raise SystemExit("unsupported Stage-7 probe configuration")
    asset = require_mapping(config.get("asset"), "asset")
    camera = require_mapping(config.get("camera"), "camera")
    motion = require_mapping(config.get("motion"), "motion")
    collision_config = require_mapping(config.get("collision_probe"), "collision_probe")
    map_name = require_string(config.get("map_name"), "map_name")
    route_id = require_string(config.get("route_id"), "route_id")
    camera_name = require_string(camera.get("name"), "camera.name")
    if camera_name != "ring_front_center":
        raise SystemExit("this minimal probe supports only ring_front_center")
    fixed_delta_s = require_number(motion.get("fixed_delta_seconds"), "motion.fixed_delta_seconds")
    sensor_tick_s = require_number(camera.get("sensor_tick_seconds"), "camera.sensor_tick_seconds")
    if fixed_delta_s <= 0.0 or sensor_tick_s <= 0.0 or abs(sensor_tick_s / fixed_delta_s - round(sensor_tick_s / fixed_delta_s)) > 1e-9:
        raise SystemExit("sensor tick must be a positive integer multiple of fixed delta")
    sample_count = int(require_number(camera.get("motion_sample_count"), "camera.motion_sample_count"))
    if sample_count < 2:
        raise SystemExit("camera.motion_sample_count must be at least two")

    calibration_path = resolve_path(require_string(camera.get("calibration"), "camera.calibration"))
    calibration = load_object(calibration_path)
    verify_source_files(calibration_path, calibration)
    calibration_by_name = {item["sensor_name"]: item for item in calibration["cameras"]}
    if camera_name not in calibration_by_name:
        raise RuntimeError(f"selected camera is absent from calibration: {camera_name}")
    routes_run = resolve_path(require_string(config.get("approved_routes_run"), "approved_routes_run"))
    weather_source = load_object(resolve_path(require_string(config.get("weather_source_config"), "weather_source_config")))
    weather_id = require_string(config.get("weather_id"), "weather_id")
    weather_profiles = require_mapping(weather_source.get("weather_profiles"), "weather_profiles")
    weather_profile = require_mapping(weather_profiles.get(weather_id), f"weather_profiles.{weather_id}")
    scene_spec_input: dict[str, object] | None = None
    resolved_animal_scene: dict[str, object] | None = None
    api_provenance: dict[str, object] | None = None
    if args.scene_spec is not None:
        raw_scene_spec = args.scene_spec.resolve().read_text()
        scene_spec = parse_scene_spec_json(raw_scene_spec)
        scene_config = load_stage7_config(resolve_path(require_string(config.get("scene_spec_config"), "scene_spec_config")))
        resolved_scene = resolve_animal_scene_spec(
            scene_spec,
            scene_config,
            load_stage7_route(PROJECT_ROOT, scene_config, scene_spec.route_id),
        )
        if scene_spec.map_name != map_name or scene_spec.route_id != route_id or scene_spec.weather_id != weather_id:
            raise RuntimeError("SceneSpec disagrees with the fixed grounded-probe map, route, or weather")
        scene_spec_input = scene_spec.as_dict()
        resolved_animal_scene = resolved_scene.as_dict()
        if args.api_attempt_result is not None:
            attempt_path = args.api_attempt_result.resolve()
            attempt = load_object(attempt_path)
            if (
                attempt.get("status") != "passed"
                or attempt.get("result_kind") != "scene_spec"
                or args.scene_spec.resolve() != (attempt_path.parent / "scene_spec.json").resolve()
            ):
                raise RuntimeError("--api-attempt-result must be a passed adapter result owning this exact scene_spec.json")
            api_provenance = {
                "kind": "api_validated_scene_spec",
                "attempt_result_path": attempt_path.as_posix(),
                "provider": attempt.get("provider"),
                "model": attempt.get("model"),
                "api_latency_s": attempt.get("api_latency_s"),
                "local_validation_s": attempt.get("local_validation_s"),
                "response_sha256": attempt.get("response_sha256"),
            }

    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout)
    world: carla.World | None = None
    original_settings: dict[str, object] | None = None
    ego: carla.Vehicle | None = None
    deer: carla.Actor | None = None
    collision_sensor: carla.Sensor | None = None
    sensors: list[SensorRuntime] = []
    collisions: list[dict[str, object]] = []
    stopped_sensor_ids: set[int] = set()
    started_wall = time.monotonic()
    try:
        available_maps = list(client.get_available_maps())
        resolved_map = next((item for item in available_maps if short_map_name(item).lower() == map_name.lower()), None)
        if resolved_map is None:
            raise RuntimeError(f"required map is not available: {map_name}")
        world = client.load_world(resolved_map, reset_settings=False, map_layers=carla.MapLayer.All)
        original_settings = configure_synchronous_world(world)
        map_ = world.get_map()
        road_lines = hide_road_lines(world)
        weather = apply_weather(world, weather_id, weather_profile)
        index = load_object(routes_run / "revised_routes.json")
        route_item = next((item for item in index["routes"] if item["route_id"] == route_id), None)
        if not isinstance(route_item, dict):
            raise RuntimeError(f"route is absent from approved revision: {route_id}")
        route = load_route(map_, routes_run / str(route_item["path"]), map_name, float(index["dense_step_m"]))
        library = world.get_blueprint_library()
        expected_blueprints = [require_string(item, "asset.expected_animal_blueprints[]") for item in asset["expected_animal_blueprints"]]
        observed_blueprints = sorted(item.id for item in library.filter("static.prop.*") if item.id in expected_blueprints)
        missing_blueprints = sorted(set(expected_blueprints) - set(observed_blueprints))
        deer_blueprint_id = require_string(asset.get("blueprint_id"), "asset.blueprint_id")
        expected_semantic_class_id = int(require_number(asset.get("expected_semantic_class_id"), "asset.expected_semantic_class_id"))
        if not 0 <= expected_semantic_class_id <= 255:
            raise RuntimeError("asset.expected_semantic_class_id must be an unsigned byte")
        runtime_dynamic_class_id = int(carla.CityObjectLabel.Dynamic)
        if expected_semantic_class_id != runtime_dynamic_class_id:
            raise RuntimeError(
                f"configured semantic class {expected_semantic_class_id} does not match "
                f"CARLA Dynamic={runtime_dynamic_class_id}"
            )
        if deer_blueprint_id not in observed_blueprints:
            raise RuntimeError(f"required imported deer blueprint is absent: {deer_blueprint_id}")
        deer_blueprint = library.find(deer_blueprint_id)
        ego_blueprint_id = require_string(config.get("ego_blueprint"), "ego_blueprint")
        ego_blueprint = library.find(ego_blueprint_id)
        ego = spawn_at_route_start(world, ego_blueprint, route)
        world.tick()
        if world.get_snapshot().find(ego.id) is None:
            raise RuntimeError("ego is absent after spawn tick")
        physics = ego.get_physics_control()
        wheel_world_cm = [[wheel.position.x, wheel.position.y, wheel.position.z] for wheel in physics.wheels]
        inverse_ego_matrix = ego.get_transform().get_inverse_matrix()
        wheel_local_m = [
            homogeneous_transform_point(inverse_ego_matrix, (position[0] / 100.0, position[1] / 100.0, position[2] / 100.0))
            for position in wheel_world_cm
        ]
        rear_axle, wheel_positions_m = rear_axle_midpoint_m([[value * 100.0 for value in point] for point in wheel_local_m])
        bbox_centre = tuple(float(value) for value in (ego.bounding_box.location.x, ego.bounding_box.location.y, ego.bounding_box.location.z))
        bbox_extent = tuple(float(value) for value in (ego.bounding_box.extent.x, ego.bounding_box.extent.y, ego.bounding_box.extent.z))
        sensor_transform, applied_camera = applied_camera_configuration(
            calibration_by_name[camera_name], rear_axle, require_number(camera.get("mount_z_offset_m"), "camera.mount_z_offset_m"), bbox_centre, bbox_extent
        )
        events: queue.Queue[tuple[str, carla.Image]] = queue.Queue()
        for modality in ("rgb", "semantic"):
            sensor_actor = world.spawn_actor(
                configure_sensor_blueprint(library, modality, applied_camera, sensor_tick_s),
                sensor_transform,
                attach_to=ego,
                attachment_type=carla.AttachmentType.Rigid,
            )
            if not isinstance(sensor_actor, carla.Sensor):
                raise RuntimeError(f"{modality} actor is not a sensor")
            key = f"{modality}:{camera_name}"
            runtime = SensorRuntime(key, camera_name, modality, sensor_actor, int(applied_camera["image_width_px"]), int(applied_camera["image_height_px"]))
            sensors.append(runtime)
            sensor_actor.listen(lambda image, sensor_key=key: events.put((sensor_key, image)))
        collision_sensor = world.spawn_actor(library.find("sensor.other.collision"), carla.Transform(), attach_to=ego)
        if not isinstance(collision_sensor, carla.Sensor):
            raise RuntimeError("collision actor is not a sensor")
        collision_sensor.listen(lambda event: collisions.append(collision_record(event)))

        pending: dict[int, dict[str, carla.Image]] = {}
        first_seen: dict[int, float] = {}
        snapshots: dict[int, carla.WorldSnapshot] = {}
        sensor_timeout_s = args.timeout
        warmup_end_s = float(world.get_snapshot().timestamp.elapsed_seconds) + require_number(camera.get("warmup_seconds"), "camera.warmup_seconds")
        baseline: dict[str, object] | None = None
        while baseline is None:
            frame, images, snapshot = wait_for_pair(world, events, pending, first_seen, snapshots, sensor_timeout_s)
            if float(snapshot.timestamp.elapsed_seconds) >= warmup_end_s:
                baseline = save_pair(
                    run_dir, "baseline", 0, frame, images, snapshot, ego.id, {expected_semantic_class_id}
                )

        anchor_progress = require_number(motion.get("anchor_progress_m"), "motion.anchor_progress_m")
        start_offset = require_number(motion.get("start_lateral_offset_m"), "motion.start_lateral_offset_m")
        end_offset = require_number(motion.get("end_lateral_offset_m"), "motion.end_lateral_offset_m")
        speed_mps = require_number(motion.get("speed_mps"), "motion.speed_mps")
        if scene_spec_input is not None:
            animal_input = scene_spec_input["animal"]
            assert isinstance(animal_input, dict)
            anchor_input, trajectory_input = animal_input["anchor"], animal_input["trajectory"]
            assert isinstance(anchor_input, dict) and isinstance(trajectory_input, dict)
            anchor_progress = require_number(anchor_input["route_progress_m"], "SceneSpec.animal.anchor.route_progress_m")
            start_offset = require_number(trajectory_input["start_lateral_offset_m"], "SceneSpec.animal.trajectory.start_lateral_offset_m")
            end_offset = require_number(trajectory_input["end_lateral_offset_m"], "SceneSpec.animal.trajectory.end_lateral_offset_m")
            speed_mps = require_number(animal_input["speed_mps"], "SceneSpec.animal.speed_mps")
        z_offset_m = require_number(motion.get("spawn_z_offset_m"), "motion.spawn_z_offset_m")
        if speed_mps <= 0.0 or start_offset == end_offset:
            raise RuntimeError("motion requires positive speed and distinct lateral endpoints")
        start_transform = route_pose(route, anchor_progress, start_offset, z_offset_m)
        end_transform = route_pose(route, anchor_progress, end_offset, z_offset_m)
        cross_yaw = math.degrees(math.atan2(end_transform.location.y - start_transform.location.y, end_transform.location.x - start_transform.location.x))
        start_transform = copy_transform(start_transform, yaw_deg=cross_yaw)
        end_transform = copy_transform(end_transform, yaw_deg=cross_yaw)
        deer = world.try_spawn_actor(deer_blueprint, start_transform)
        if deer is None:
            raise RuntimeError("CARLA rejected the route-relative deer start transform")
        world.tick()
        # CARLA 0.9.16 does not expose semantic_tags for this imported static
        # prop through the Python Actor API.  The package documents Dynamic;
        # validation below therefore uses its explicit raw image class ID.
        reported_deer_tags = sorted(int(tag) for tag in deer.semantic_tags)
        deer_tags = {expected_semantic_class_id}
        vertices = deer.bounding_box.get_world_vertices(deer.get_transform())
        ground_waypoint = map_.get_waypoint(start_transform.location, project_to_road=True, lane_type=carla.LaneType.Any)
        if ground_waypoint is None:
            raise RuntimeError("could not project deer start to a map waypoint")
        ground_height = float(ground_waypoint.transform.location.z)
        bbox_ground_min = min(float(vertex.z) for vertex in vertices)
        motion_start_s = float(world.get_snapshot().timestamp.elapsed_seconds)
        cross_distance = transform_distance_m(start_transform, end_transform)
        motion_records: list[dict[str, object]] = []
        previous_actual: carla.Transform | None = None

        def step_animal(snapshot: carla.WorldSnapshot) -> None:
            nonlocal previous_actual
            assert deer is not None
            elapsed = max(0.0, float(snapshot.timestamp.elapsed_seconds) - motion_start_s)
            distance = min(cross_distance, elapsed * speed_mps)
            fraction = distance / cross_distance
            transform = carla.Transform(
                carla.Location(
                    x=start_transform.location.x + fraction * (end_transform.location.x - start_transform.location.x),
                    y=start_transform.location.y + fraction * (end_transform.location.y - start_transform.location.y),
                    z=start_transform.location.z + fraction * (end_transform.location.z - start_transform.location.z),
                ),
                carla.Rotation(yaw=cross_yaw),
            )
            deer.set_transform(transform)
            motion_records.append(
                {
                    "command_frame": int(snapshot.frame),
                    "command_simulation_time_s": float(snapshot.timestamp.elapsed_seconds),
                    "requested_transform": transform_to_dict(transform),
                }
            )

        samples: list[dict[str, object]] = []
        while len(samples) < sample_count:
            frame, images, snapshot = wait_for_pair(world, events, pending, first_seen, snapshots, sensor_timeout_s, step_animal)
            deer_snapshot = snapshot.find(deer.id)
            if deer_snapshot is None:
                raise RuntimeError("deer is absent from a motion snapshot")
            actual = deer_snapshot.get_transform()
            step_m = transform_distance_m(previous_actual, actual) if previous_actual is not None else 0.0
            sample = save_pair(run_dir, "motion", len(samples), frame, images, snapshot, ego.id, deer_tags)
            sample["animal_transform"] = transform_to_dict(actual)
            sample["animal_step_m_since_previous_sensor_sample"] = step_m
            samples.append(sample)
            previous_actual = actual
            # Keep snapshot bookkeeping bounded while retaining enough delivery lag.
            snapshots = {key: value for key, value in snapshots.items() if key >= frame - 80}

        collision_transform = route_pose(
            route,
            require_number(collision_config.get("anchor_progress_m"), "collision_probe.anchor_progress_m"),
            require_number(collision_config.get("lateral_offset_m"), "collision_probe.lateral_offset_m"),
            z_offset_m,
        )
        deer.set_transform(copy_transform(collision_transform, yaw_deg=float(collision_transform.rotation.yaw)))
        collision_start_s = float(world.get_snapshot().timestamp.elapsed_seconds)
        collision_distance_trace: list[dict[str, object]] = []
        while float(world.get_snapshot().timestamp.elapsed_seconds) - collision_start_s < require_number(collision_config.get("maximum_simulation_seconds"), "collision_probe.maximum_simulation_seconds"):
            ego.apply_control(carla.VehicleControl(throttle=require_number(collision_config.get("throttle"), "collision_probe.throttle")))
            frame = int(world.tick())
            snapshot = world.get_snapshot()
            deer_snapshot = snapshot.find(deer.id)
            ego_snapshot = snapshot.find(ego.id)
            if deer_snapshot is None or ego_snapshot is None:
                raise RuntimeError("ego or deer disappeared during collision probe")
            collision_distance_trace.append(
                {
                    "frame": frame,
                    "simulation_time_s": float(snapshot.timestamp.elapsed_seconds),
                    "distance_m": math.hypot(
                        float(deer_snapshot.get_transform().location.x - ego_snapshot.get_transform().location.x),
                        float(deer_snapshot.get_transform().location.y - ego_snapshot.get_transform().location.y),
                    ),
                }
            )
            if any(event["other_actor_id"] == int(deer.id) for event in collisions):
                break
        for _ in range(max(1, round(1.0 / fixed_delta_s))):
            ego.apply_control(carla.VehicleControl(brake=1.0, hand_brake=True))
            world.tick()

        maximum_sensor_step = max((float(sample["animal_step_m_since_previous_sensor_sample"]) for sample in samples[1:]), default=0.0)
        maximum_per_tick_step = speed_mps * fixed_delta_s * require_number(motion.get("maximum_step_multiplier"), "motion.maximum_step_multiplier")
        commanded_transforms = [
            carla.Transform(
                carla.Location(**record["requested_transform"]["location"]),
                carla.Rotation(**record["requested_transform"]["rotation"]),
            )
            for record in motion_records
        ]
        maximum_command_step = max(
            (transform_distance_m(first, second) for first, second in zip(commanded_transforms, commanded_transforms[1:])),
            default=0.0,
        )
        motion_first = samples[0]["animal_transform"]
        motion_last = samples[-1]["animal_transform"]
        first_transform = carla.Transform(
            carla.Location(**motion_first["location"]), carla.Rotation(**motion_first["rotation"])
        )
        last_transform = carla.Transform(
            carla.Location(**motion_last["location"]), carla.Rotation(**motion_last["rotation"])
        )
        total_sensor_motion_m = transform_distance_m(first_transform, last_transform)
        end_distance_m = transform_distance_m(last_transform, end_transform)
        baseline_dynamic_pixels = int(baseline["animal_semantic_tag_pixels"][str(expected_semantic_class_id)])
        support_pixels = [sum(int(value) for value in sample["animal_semantic_tag_pixels"].values()) for sample in samples]
        semantic_delta_pixels = [value - baseline_dynamic_pixels for value in support_pixels]
        semantic_visible = max(semantic_delta_pixels, default=0) > 0
        validation = {
            "checks": {
                "all_expected_animal_blueprints_present": not missing_blueprints,
                "deer_blueprint_present": deer_blueprint_id in observed_blueprints,
                "front_rgb_semantic_pair_count": len(samples) == sample_count,
                "semantic_support_observed": semantic_visible,
                "ground_contact_height_within_tolerance": abs(bbox_ground_min - ground_height) <= 0.03,
                "motion_observed": total_sensor_motion_m >= require_number(motion.get("minimum_total_motion_m"), "motion.minimum_total_motion_m"),
                "sensor_step_within_expected_bound": maximum_sensor_step <= sensor_tick_s * speed_mps * require_number(motion.get("maximum_step_multiplier"), "motion.maximum_step_multiplier") + 0.02,
                "per_tick_kinematic_step_within_expected_bound": maximum_command_step <= maximum_per_tick_step + 1e-6,
                "configured_trajectory_endpoint_reached": end_distance_m <= 0.02,
                "collision_probe_completed": bool(collision_distance_trace),
            },
            "collision_with_deer": any(event["other_actor_id"] == int(deer.id) for event in collisions),
            "expected_semantic_class_ids_used_for_mask": sorted(deer_tags),
            "actor_semantic_tags_reported_by_api": reported_deer_tags,
            "semantic_support_pixels_by_motion_sample": support_pixels,
            "semantic_support_delta_from_baseline_pixels": semantic_delta_pixels,
            "motion": {
                "configured_speed_mps": speed_mps,
                "configured_fixed_delta_seconds": fixed_delta_s,
                "configured_maximum_per_tick_step_m": maximum_per_tick_step,
                "maximum_commanded_per_tick_step_m": maximum_command_step,
                "maximum_sensor_interval_step_m": maximum_sensor_step,
                "total_sensor_motion_m": total_sensor_motion_m,
                "distance_to_configured_endpoint_m": end_distance_m,
            },
            "height": {
                "route_ground_z_m": ground_height,
                "deer_bbox_min_z_m": bbox_ground_min,
                "bbox_min_minus_ground_m": bbox_ground_min - ground_height,
                "bounding_box_extent_m": [float(deer.bounding_box.extent.x), float(deer.bounding_box.extent.y), float(deer.bounding_box.extent.z)],
            },
        }
        validation["passed"] = all(validation["checks"].values())
        write_json(run_dir / "asset_provenance.json", {"asset": asset, "base_image": config["base_image"], "derived_image": config["derived_image"]})
        if scene_spec_input is not None:
            write_json(run_dir / "scene_spec.json", scene_spec_input)
            write_json(run_dir / "resolved_scene.json", resolved_animal_scene)
            write_json(run_dir / "scene_input.json", {"scene_spec_sha256": canonical_json_sha256(scene_spec_input), "api_provenance": api_provenance})
        write_json(run_dir / "calibration.json", {"selected_camera": applied_camera, "rear_axle_origin_relative_to_actor_m": list(rear_axle), "wheel_positions_relative_to_actor_m": [list(value) for value in wheel_positions_m]})
        write_json(run_dir / "baseline_capture.json", baseline)
        write_json(run_dir / "motion_samples.json", {"samples": samples})
        write_json(run_dir / "animal_motion.json", {"start_transform": transform_to_dict(start_transform), "end_transform": transform_to_dict(end_transform), "records": motion_records, "motion_samples": samples})
        write_json(run_dir / "collision_probe.json", {"target_transform": transform_to_dict(collision_transform), "distance_trace": collision_distance_trace, "events": collisions})
        write_json(run_dir / "probe_validation.json", validation)
        write_json(run_dir / "scene.json", {"map_name": map_.name, "weather": weather, "road_line_operation": road_lines, "route_id": route.route_id, "debug_drawings": "none"})
        update_metadata(
            metadata_path,
            carla_server_version=client.get_server_version(),
            carla_client_version=client.get_client_version(),
            selected_camera_names=[camera_name],
            sensor_count=len(sensors),
            animal_blueprint=deer_blueprint_id,
            scene_spec_sha256=canonical_json_sha256(scene_spec_input) if scene_spec_input is not None else None,
            api_call_made=api_provenance is not None,
            probe_validation_passed=bool(validation["passed"]),
            wall_duration_s=time.monotonic() - started_wall,
        )
        if not validation["passed"]:
            raise RuntimeError(f"Stage-7 probe checks failed: {validation['checks']}")
    finally:
        for sensor in sensors:
            if int(sensor.actor.id) not in stopped_sensor_ids:
                sensor.actor.stop()
            sensor.actor.destroy()
        if collision_sensor is not None:
            collision_sensor.stop()
            collision_sensor.destroy()
        if deer is not None:
            deer.destroy()
        if ego is not None:
            ego.destroy()
        if world is not None and original_settings is not None:
            restore_world_settings(world, original_settings)


if __name__ == "__main__":
    main()
