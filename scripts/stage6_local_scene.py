#!/usr/bin/env python3
"""Apply and replay one pre-validated Stage-6 SceneSpec without an LLM API call.

The command creates a fresh ``Town01_Opt`` world for every invocation.  It
then reapplies the tested road-line operation, validates a route-relative
SceneSpec against the live map and blueprints, creates only allow-listed parked
vehicles, saves before/after views, records three complete AV2 rig samples, and
finishes the straight control route with Traffic Manager.  A rerun with the
same saved SceneSpec is therefore a replay, not another model call.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import queue
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import carla

from stage2_autopilot_routes import (
    RouteDefinition,
    collision_record,
    load_route,
    nearest_route_state,
    spawn_at_route_start,
    stop_after_completion,
)
from stage2_routes import (
    configure_synchronous_world,
    hide_road_lines,
    restore_world_settings,
    short_map_name,
    transform_to_dict,
    update_metadata,
    write_json,
)
from stage3_geometry import homogeneous_transform_point
from stage3_recording import CAMERA_ORDER, SensorRuntime, pose_from_snapshot, verify_source_files
from stage4_baseline import (
    apply_weather,
    calibration_and_sensors,
    drain_sensor_events,
    prepare_sample_buffers,
    save_prepared_sample,
)
from stage6_scene_spec import (
    Refusal,
    ResolvedEdit,
    ResolvedScene,
    SceneSpecError,
    canonical_json_sha256,
    load_route_geometry,
    load_stage6_config,
    parse_response_json,
    resolve_scene_spec,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError(f"expected a JSON object: {path}")
    return value


def relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def load_api_attempt_provenance(path: Path, scene_spec_path: Path, run_dir: Path) -> dict[str, object]:
    """Bind an executor replay to one previously validated adapter attempt.

    The adapter has already stored the raw provider response.  This function
    rejects an arbitrary JSON file being labelled as an API result, but still
    leaves the SceneSpec itself as passive data for the normal executor path.
    """
    record = load_json_object(path)
    if record.get("status") != "passed" or record.get("result_kind") != "scene_spec":
        raise RuntimeError("API provenance must name a passed SceneSpec adapter attempt")
    relative_scene_path = record.get("scene_spec_path")
    if relative_scene_path != "scene_spec.json":
        raise RuntimeError("API provenance has an unexpected scene_spec_path")
    expected_spec_path = (path.parent / str(relative_scene_path)).resolve()
    if expected_spec_path != scene_spec_path.resolve():
        raise RuntimeError("--scene-spec does not match the saved API adapter attempt")
    if not isinstance(record.get("provider"), str) or not isinstance(record.get("model"), str):
        raise RuntimeError("API provenance lacks provider or model")
    api_latency = record.get("api_latency_s")
    local_latency = record.get("local_validation_s")
    if not isinstance(api_latency, (int, float)) or not isinstance(local_latency, (int, float)):
        raise RuntimeError("API provenance lacks numeric API/local validation timing")
    return {
        "source_path": scene_spec_path.resolve().as_posix(),
        "source_attempt_result_path": relative_or_absolute(path, run_dir),
        "kind": "api_validated_scene_spec",
        "api_call_made": True,
        "provider": record["provider"],
        "model": record["model"],
        "api_latency_s": float(api_latency),
        "local_validation_s": float(local_latency),
        "reported_usage": record.get("reported_usage"),
        "response_sha256": record.get("response_sha256"),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def profile_from_config(project_root: Path, config: dict[str, object], weather_id: str) -> tuple[dict[str, Any], Path]:
    source_path = project_root / str(config["weather_source_config"])
    source = load_json_object(source_path)
    profiles = source.get("weather_profiles")
    if not isinstance(profiles, dict) or weather_id not in profiles:
        raise RuntimeError(f"weather profile {weather_id!r} is absent from {source_path}")
    profile = profiles[weather_id]
    if not isinstance(profile, dict):
        raise RuntimeError(f"weather profile {weather_id!r} is malformed")
    return profile, source_path


def observer_transform(edit: ResolvedEdit) -> carla.Transform:
    """A deterministic nadir camera centred on the first proposed edit."""
    return carla.Transform(
        carla.Location(x=edit.x, y=edit.y, z=edit.z + 25.0),
        carla.Rotation(pitch=-90.0, yaw=edit.yaw_deg),
    )


def capture_observer_rgb(world: carla.World, transform: carla.Transform, path: Path) -> dict[str, object]:
    """Save one raw RGB observer view without reloading or changing the scene."""
    blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
    for key, value in {"image_size_x": "800", "image_size_y": "600", "fov": "90", "sensor_tick": "0.0"}.items():
        if blueprint.has_attribute(key):
            blueprint.set_attribute(key, value)
    images: queue.Queue[carla.Image] = queue.Queue()
    camera = world.spawn_actor(blueprint, transform)
    if not isinstance(camera, carla.Sensor):
        raise RuntimeError("observer camera is not a CARLA sensor")
    camera.listen(images.put)
    try:
        frame = int(world.tick())
        deadline = time.monotonic() + 30.0
        image: carla.Image | None = None
        while time.monotonic() < deadline:
            try:
                candidate = images.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty:
                break
            if int(candidate.frame) == frame:
                image = candidate
                break
            if int(candidate.frame) > frame:
                raise RuntimeError(f"observer camera skipped expected frame {frame}")
        if image is None:
            raise TimeoutError(f"observer camera did not return frame {frame}")
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save_to_disk(str(path), carla.ColorConverter.Raw)
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"observer frame was not written: {path}")
        return {
            "path": path.as_posix(),
            "frame": int(image.frame),
            "simulation_time_s": float(image.timestamp),
            "resolution": {"width": int(image.width), "height": int(image.height)},
            "sha256": sha256_file(path),
            "camera_transform": transform_to_dict(transform),
        }
    finally:
        camera.stop()
        camera.destroy()


def actor_radius_m(actor: carla.Actor) -> float:
    extent = actor.bounding_box.extent
    return math.hypot(float(extent.x), float(extent.y))


def actor_ground_centre(actor: carla.Actor) -> carla.Location:
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if not vertices:
        return actor.get_location()
    return carla.Location(
        x=sum(float(vertex.x) for vertex in vertices) / len(vertices),
        y=sum(float(vertex.y) for vertex in vertices) / len(vertices),
        z=sum(float(vertex.z) for vertex in vertices) / len(vertices),
    )


def actors_overlap(first: carla.Actor, second: carla.Actor, margin_m: float = 0.1) -> bool:
    first_centre, second_centre = actor_ground_centre(first), actor_ground_centre(second)
    distance = math.hypot(float(first_centre.x - second_centre.x), float(first_centre.y - second_centre.y))
    return distance + margin_m < actor_radius_m(first) + actor_radius_m(second)


def target_is_on_driving_lane(map_: carla.Map, transform: carla.Transform) -> bool:
    waypoint = map_.get_waypoint(
        transform.location,
        project_to_road=False,
        lane_type=carla.LaneType.Driving,
    )
    return waypoint is not None


def live_preflight(
    world: carla.World,
    map_: carla.Map,
    library: carla.BlueprintLibrary,
    resolved: ResolvedScene,
    ego: carla.Vehicle,
) -> list[dict[str, object]]:
    """Reject unavailable blueprints, road placement, and known actor conflicts."""
    existing = list(world.get_actors().filter("vehicle.*"))
    records: list[dict[str, object]] = []
    for edit in resolved.edits:
        try:
            blueprint = library.find(edit.blueprint_id)
        except RuntimeError as exc:
            raise SceneSpecError("blueprint_unavailable", f"$.edits[{edit.edit_index}].blueprint_id", str(exc)) from exc
        if blueprint.id != edit.blueprint_id:
            raise SceneSpecError("blueprint_unavailable", f"$.edits[{edit.edit_index}].blueprint_id", "exact blueprint was not found")
        transform = carla.Transform(
            carla.Location(x=edit.x, y=edit.y, z=edit.z),
            carla.Rotation(roll=0.0, pitch=0.0, yaw=edit.yaw_deg),
        )
        if target_is_on_driving_lane(map_, transform):
            raise SceneSpecError(
                "spatial_conflict",
                f"$.edits[{edit.edit_index}]",
                "resolved parked-vehicle centre lies on a driving lane",
            )
        distance_to_ego = math.hypot(
            float(transform.location.x - ego.get_location().x),
            float(transform.location.y - ego.get_location().y),
        )
        records.append(
            {
                "edit_index": edit.edit_index,
                "blueprint_available": True,
                "target_on_driving_lane": False,
                "target_distance_to_ego_m": distance_to_ego,
                "existing_vehicle_actor_ids": [int(actor.id) for actor in existing],
                "proposed_transform": transform_to_dict(transform),
            }
        )
    return records


def spawn_parked_vehicles(
    world: carla.World,
    map_: carla.Map,
    library: carla.BlueprintLibrary,
    resolved: ResolvedScene,
    ego: carla.Vehicle,
) -> tuple[list[carla.Vehicle], list[dict[str, object]]]:
    parked: list[carla.Vehicle] = []
    records: list[dict[str, object]] = []
    try:
        for edit in resolved.edits:
            blueprint = library.find(edit.blueprint_id)
            if blueprint.has_attribute("role_name"):
                blueprint.set_attribute("role_name", f"stage6_parked_{edit.edit_index:02d}")
            transform = carla.Transform(
                carla.Location(x=edit.x, y=edit.y, z=edit.z),
                carla.Rotation(roll=0.0, pitch=0.0, yaw=edit.yaw_deg),
            )
            actor = world.try_spawn_actor(blueprint, transform)
            if actor is None or not isinstance(actor, carla.Vehicle):
                raise RuntimeError(f"edit {edit.edit_index}: CARLA could not spawn parked vehicle")
            actor.set_simulate_physics(False)
            world.tick()
            if target_is_on_driving_lane(map_, actor.get_transform()):
                raise RuntimeError(f"edit {edit.edit_index}: spawned vehicle centre is on a driving lane")
            for other in [ego, *parked]:
                if actors_overlap(actor, other):
                    raise RuntimeError(f"edit {edit.edit_index}: spawned vehicle overlaps actor {other.id}")
            parked.append(actor)
            records.append(
                {
                    "edit_index": edit.edit_index,
                    "actor_id": int(actor.id),
                    "type_id": actor.type_id,
                    "semantic_tags": [int(tag) for tag in actor.semantic_tags],
                    "physics_enabled": False,
                    "actual_transform": transform_to_dict(actor.get_transform()),
                    "bounding_box": {
                        "centre_relative_to_actor_m": {
                            "x": float(actor.bounding_box.location.x),
                            "y": float(actor.bounding_box.location.y),
                            "z": float(actor.bounding_box.location.z),
                        },
                        "extent_m": {
                            "x": float(actor.bounding_box.extent.x),
                            "y": float(actor.bounding_box.extent.y),
                            "z": float(actor.bounding_box.extent.z),
                        },
                    },
                }
            )
        return parked, records
    except Exception:
        for actor in parked:
            actor.destroy()
        raise


def project_actor_to_camera(
    actor: carla.Actor,
    camera_transform: carla.Transform,
    width: int,
    height: int,
    horizontal_fov_deg: float,
) -> dict[str, object]:
    """Project a parked actor bounding box using CARLA's pinhole convention."""
    focal = width / (2.0 * math.tan(math.radians(horizontal_fov_deg) / 2.0))
    inverse = camera_transform.get_inverse_matrix()
    projected: list[tuple[float, float]] = []
    for vertex in actor.bounding_box.get_world_vertices(actor.get_transform()):
        forward, right, up = homogeneous_transform_point(inverse, (float(vertex.x), float(vertex.y), float(vertex.z)))
        if forward <= 0.1:
            continue
        projected.append((width / 2.0 + focal * right / forward, height / 2.0 - focal * up / forward))
    if not projected:
        return {"projectable": False, "reason": "all bounding-box vertices are behind the camera"}
    left = max(0, math.floor(min(item[0] for item in projected)))
    right = min(width - 1, math.ceil(max(item[0] for item in projected)))
    top = max(0, math.floor(min(item[1] for item in projected)))
    bottom = min(height - 1, math.ceil(max(item[1] for item in projected)))
    if left > right or top > bottom:
        return {"projectable": False, "reason": "projected bounding box lies outside the image"}
    return {
        "projectable": True,
        "pixel_bounds": {"left": left, "right": right, "top": top, "bottom": bottom},
        "projected_vertex_count": len(projected),
    }


def semantic_support_pixels(image: carla.Image, bounds: dict[str, object], tags: set[int]) -> int:
    left, right = int(bounds["left"]), int(bounds["right"])
    top, bottom = int(bounds["top"]), int(bounds["bottom"])
    raw = memoryview(image.raw_data)
    matches = 0
    for row in range(top, bottom + 1):
        start = (row * image.width + left) * 4 + 2
        stop = (row * image.width + right + 1) * 4
        matches += sum(value in tags for value in raw[start:stop:4])
    return matches


def observe_visibility(
    images: dict[str, carla.Image],
    snapshot: carla.WorldSnapshot,
    runtimes: dict[str, SensorRuntime],
    parked: list[carla.Vehicle],
) -> dict[str, dict[str, dict[str, object]]]:
    result: dict[str, dict[str, dict[str, object]]] = {}
    for actor in parked:
        actor_record: dict[str, dict[str, object]] = {}
        tags = {int(tag) for tag in actor.semantic_tags}
        for camera_name in CAMERA_ORDER:
            runtime = runtimes[f"semantic:{camera_name}"]
            sensor_snapshot = snapshot.find(runtime.actor.id)
            if sensor_snapshot is None:
                raise RuntimeError(f"camera actor {runtime.actor.id} is absent from image snapshot")
            projection = project_actor_to_camera(
                actor,
                sensor_snapshot.get_transform(),
                runtime.width,
                runtime.height,
                float(runtime.actor.attributes["fov"]),
            )
            if projection.get("projectable"):
                projection["semantic_support_pixels"] = semantic_support_pixels(
                    images[f"semantic:{camera_name}"],
                    dict(projection["pixel_bounds"]),
                    tags,
                )
            else:
                projection["semantic_support_pixels"] = 0
            actor_record[camera_name] = projection
        result[str(actor.id)] = actor_record
    return result


def merge_visibility(
    aggregate: dict[str, dict[str, dict[str, object]]],
    sample_index: int,
    observed: dict[str, dict[str, dict[str, object]]],
) -> None:
    for actor_id, cameras in observed.items():
        actor_summary = aggregate.setdefault(actor_id, {})
        for camera_name, record in cameras.items():
            summary = actor_summary.setdefault(
                camera_name,
                {"ever_projectable": False, "maximum_semantic_support_pixels": 0, "supporting_sample_indices": []},
            )
            summary["ever_projectable"] = bool(summary["ever_projectable"]) or bool(record.get("projectable"))
            pixels = int(record.get("semantic_support_pixels", 0))
            summary["maximum_semantic_support_pixels"] = max(int(summary["maximum_semantic_support_pixels"]), pixels)
            if pixels > 0:
                indices = list(summary["supporting_sample_indices"])
                indices.append(sample_index)
                summary["supporting_sample_indices"] = sorted(set(indices))


def visibility_passes(visibility: dict[str, dict[str, dict[str, object]]], parked: list[carla.Vehicle]) -> bool:
    return all(
        any(int(camera["maximum_semantic_support_pixels"]) > 0 for camera in visibility.get(str(actor.id), {}).values())
        for actor in parked
    )


def record_rig_and_drive(
    world: carla.World,
    traffic_manager: carla.TrafficManager,
    traffic_manager_port: int,
    route: RouteDefinition,
    ego: carla.Vehicle,
    parked: list[carla.Vehicle],
    run_dir: Path,
    calibration_path: Path,
    calibration: dict[str, Any],
    config: dict[str, object],
    sensor_timeout_s: float,
) -> dict[str, object]:
    settings = config["short_validation"]
    assert isinstance(settings, dict)
    sensor_tick_s = float(settings["sensor_tick_seconds"])
    fixed_delta_s = float(settings["fixed_delta_seconds"])
    warmup_s = float(settings["warmup_seconds"])
    wanted_samples = int(settings["rig_sample_count"])
    sensor_events: queue.Queue[tuple[str, carla.Image]] = queue.Queue()
    sensors, calibration_record = calibration_and_sensors(
        world,
        ego,
        calibration_path,
        calibration,
        float(settings["mount_z_offset_m"]),
        sensor_tick_s,
        sensor_events,
    )
    collision_sensor: carla.Sensor | None = None
    stopped_sensor_ids: set[int] = set()
    collisions: list[dict[str, object]] = []
    try:
        write_json(run_dir / "calibration.json", calibration_record)
        collision_sensor = world.spawn_actor(
            world.get_blueprint_library().find("sensor.other.collision"), carla.Transform(), attach_to=ego
        )
        if not isinstance(collision_sensor, carla.Sensor):
            raise RuntimeError("collision sensor is not a CARLA sensor")
        collision_sensor.listen(lambda event: collisions.append(collision_record(event)))
        runtimes = {sensor.key: sensor for sensor in sensors}
        expected_keys = set(runtimes)
        if len(expected_keys) != 18:
            raise RuntimeError("the Stage-6 visibility run did not create all 18 sensors")
        traffic_manager.auto_lane_change(ego, False)
        traffic_manager.ignore_lights_percentage(ego, 100.0)
        traffic_manager.ignore_signs_percentage(ego, 100.0)
        traffic_manager.vehicle_percentage_speed_difference(ego, -20.0)
        ego.set_autopilot(True, traffic_manager_port)
        traffic_manager.set_route(ego, route.traffic_manager_route_instructions)

        initial_snapshot = world.get_snapshot()
        start_time_s = float(initial_snapshot.timestamp.elapsed_seconds)
        pending: dict[int, dict[str, carla.Image]] = {}
        first_event_wall: dict[int, float] = {}
        poses: dict[int, dict[str, object]] = {}
        snapshots: dict[int, carla.WorldSnapshot] = {}
        duplicate_keys: list[str] = []
        samples: list[dict[str, object]] = []
        visibility: dict[str, dict[str, dict[str, object]]] = {}
        per_sample_visibility: list[dict[str, object]] = []
        last_timestamp: float | None = None
        discarded_frames: list[int] = []
        while len(samples) < wanted_samples:
            frame = int(world.tick())
            snapshot = world.get_snapshot()
            if int(snapshot.frame) != frame:
                raise RuntimeError("world snapshot frame differs from synchronous tick")
            poses[frame] = pose_from_snapshot(snapshot, ego.id)
            snapshots[frame] = snapshot
            drain_sensor_events(sensor_events, pending, first_event_wall, duplicate_keys, expected_keys, sensor_timeout_s)
            for complete_frame in sorted(list(pending)):
                images = pending.pop(complete_frame)
                first_event_wall.pop(complete_frame, None)
                if complete_frame not in poses or complete_frame not in snapshots:
                    raise RuntimeError(f"sensor frame {complete_frame} lacks a same-frame ego snapshot")
                timestamps = [float(image.timestamp) for image in images.values()]
                if max(timestamps) - min(timestamps) > 1e-6:
                    raise RuntimeError(f"sensor timestamps differ within frame {complete_frame}")
                timestamp = timestamps[0]
                if abs(timestamp - float(poses[complete_frame]["simulation_time_s"])) > 1e-4:
                    raise RuntimeError(f"sensor and ego timestamps differ at frame {complete_frame}")
                if timestamp + 1e-9 < start_time_s + warmup_s:
                    discarded_frames.append(complete_frame)
                    continue
                if last_timestamp is not None and abs(timestamp - last_timestamp - sensor_tick_s) > 1e-4:
                    raise RuntimeError("accepted capture interval differs from the configured 2 Hz rate")
                sample_index = len(samples)
                observed = observe_visibility(images, snapshots[complete_frame], runtimes, parked)
                merge_visibility(visibility, sample_index, observed)
                per_sample_visibility.append(
                    {"sample_index": sample_index, "frame": complete_frame, "actors": observed}
                )
                prepared = prepare_sample_buffers(images, runtimes)
                samples.append(
                    save_prepared_sample(
                        run_dir,
                        sample_index,
                        complete_frame,
                        timestamp,
                        prepared,
                        poses[complete_frame],
                    )
                )
                last_timestamp = timestamp
                if len(samples) == wanted_samples:
                    break
            poses = {key: value for key, value in poses.items() if key >= frame - 40}
            snapshots = {key: value for key, value in snapshots.items() if key >= frame - 40}
            if collisions:
                raise RuntimeError("collision occurred during the short 18-camera capture")
        for sensor in sensors:
            sensor.actor.stop()
            stopped_sensor_ids.add(int(sensor.actor.id))
        transforms = {
            "schema_version": 1,
            "state": "complete",
            "coordinate_system": "CARLA world coordinates in metres; rotations in degrees",
            "recording_frequency_hz": 1.0 / sensor_tick_s,
            "fixed_delta_seconds": fixed_delta_s,
            "samples": samples,
        }
        write_json(run_dir / "transforms.json", transforms)
        write_json(
            run_dir / "capture_summary.json",
            {
                "selected_camera_names": list(CAMERA_ORDER),
                "sensor_count": len(sensors),
                "sample_count": len(samples),
                "image_count": len(samples) * len(sensors),
                "preview_count": len(samples) * len(CAMERA_ORDER),
                "duplicate_sensor_keys": duplicate_keys,
                "warmup_discarded_complete_frames": discarded_frames,
                "accepted_capture_span_simulation_s": (
                    float(samples[-1]["sensor_timestamp_s"]) - float(samples[0]["sensor_timestamp_s"])
                    if len(samples) > 1
                    else 0.0
                ),
            },
        )
        validator = Path(__file__).with_name("stage3_validate_dataset.py")
        subprocess.run([sys.executable, str(validator), str(run_dir), "--require-all-nine"], check=True)
        camera_validation = load_json_object(run_dir / "validation.json")

        route_trajectory: list[dict[str, object]] = []
        maximum_deviation = 0.0
        maximum_progress = 0.0
        completion: dict[str, object] | None = None
        outcome = "timeout"
        timeout_s = float(settings["route_timeout_seconds"])
        finish_radius_m = float(settings["finish_radius_m"])
        deviation_limit_m = float(settings["path_deviation_limit_m"])
        while True:
            frame = int(world.tick())
            snapshot = world.get_snapshot()
            state = nearest_route_state(route, ego.get_transform().location)
            pose = pose_from_snapshot(snapshot, ego.id)
            record = {**pose, "route_state": state}
            route_trajectory.append(record)
            maximum_deviation = max(maximum_deviation, float(state["nearest_route_distance_m"]))
            if float(state["nearest_route_distance_m"]) <= deviation_limit_m:
                maximum_progress = max(maximum_progress, float(state["nearest_route_progress_m"]))
            elapsed = float(snapshot.timestamp.elapsed_seconds) - start_time_s
            if collisions:
                outcome = "collision"
                break
            if (
                float(state["distance_to_finish_m"]) <= finish_radius_m
                and maximum_progress >= route.length_m * 0.95
            ):
                outcome = "completed"
                completion = record
                break
            if elapsed >= timeout_s:
                break
        ego.set_autopilot(False, traffic_manager_port)
        stop_check = stop_after_completion(world, ego, fixed_delta_s, duration_s=1.0)
        write_json(run_dir / "route_trajectory.json", route_trajectory)
        write_json(run_dir / "collisions.json", collisions)
        route_check = {
            "route_id": route.route_id,
            "outcome": outcome,
            "completion_record": completion,
            "collision_count": len(collisions),
            "maximum_deviation_m": maximum_deviation,
            "maximum_progress_m": maximum_progress,
            "required_completion_progress_m": route.length_m * 0.95,
            "route_length_m": route.length_m,
            "post_finish_stop": stop_check,
            "checks": {
                "completed": outcome == "completed",
                "no_collision": not collisions,
                "deviation_within_limit": maximum_deviation <= deviation_limit_m,
                "stopped": bool(stop_check["stopped"]),
            },
        }
        write_json(run_dir / "route_check.json", route_check)
        return {
            "camera_validation": camera_validation,
            "visibility": visibility,
            "per_sample_visibility": per_sample_visibility,
            "visibility_passed": visibility_passes(visibility, parked),
            "route_check": route_check,
        }
    finally:
        for sensor in sensors:
            if int(sensor.actor.id) not in stopped_sensor_ids:
                sensor.actor.stop()
            sensor.actor.destroy()
        if collision_sensor is not None:
            collision_sensor.stop()
            collision_sensor.destroy()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--scene-spec", type=Path, required=True, help="Saved manual or API SceneSpec JSON; never executable code.")
    parser.add_argument(
        "--api-attempt-result",
        type=Path,
        help="Passed attempt_result.json from stage6_api_adapter.py; binds this replay to saved API provenance.",
    )
    parser.add_argument("--config", type=Path, default=Path("configs/stage6_scene_editing.json"))
    parser.add_argument(
        "--calibration",
        type=Path,
        default=Path("configs/av2/54bc6dbc-ebfb-3fba-b5b3-57f88b4b79ca/calibration.json"),
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--traffic-manager-port", type=int, default=8000)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--sensor-timeout-s", type=float, default=30.0)
    parser.add_argument("--validate-only", action="store_true", help="Run local JSON/policy checks only; do not connect to CARLA.")
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.is_file():
        raise SystemExit("run directory was not created by scripts/create_run.py")
    if args.timeout <= 0.0 or args.sensor_timeout_s <= 0.0:
        raise SystemExit("timeouts must be positive")

    config_path = (PROJECT_ROOT / args.config).resolve() if not args.config.is_absolute() else args.config.resolve()
    calibration_path = (PROJECT_ROOT / args.calibration).resolve() if not args.calibration.is_absolute() else args.calibration.resolve()
    spec_path = args.scene_spec.resolve()
    parked: list[carla.Vehicle] = []
    ego: carla.Vehicle | None = None
    world: carla.World | None = None
    original_settings: dict[str, object] | None = None
    traffic_manager: carla.TrafficManager | None = None
    started_wall = time.monotonic()
    try:
        raw_response = spec_path.read_text()
        response = parse_response_json(raw_response)
        config = load_stage6_config(config_path)
        input_record = (
            load_api_attempt_provenance(args.api_attempt_result.resolve(), spec_path, run_dir)
            if args.api_attempt_result is not None
            else {
                "source_path": spec_path.as_posix(),
                "kind": "manual_pre_api_fixture",
                "api_call_made": False,
            }
        )
        input_record["source_sha256"] = hashlib.sha256(raw_response.encode("utf-8")).hexdigest()
        write_json(run_dir / "attempt.json", input_record)
        write_json(run_dir / "raw_response.json", json.loads(raw_response))
        if isinstance(response, Refusal):
            write_json(run_dir / "refusal.json", response.as_dict())
            result = {
                "status": "refused_as_designed",
                "api_call_made": bool(input_record["api_call_made"]),
                "refusal": response.as_dict(),
                "timing": {
                    "api_latency_s": input_record.get("api_latency_s"),
                    "local_validation_and_resolution_s": input_record.get("local_validation_s"),
                    "carla_application_and_validation_wall_s": None,
                },
                "wall_duration_s": time.monotonic() - started_wall,
            }
            write_json(run_dir / "execution_result.json", result)
            update_metadata(metadata_path, state="complete", stage6_result="refused_as_designed", validation_path="execution_result.json")
            print(run_dir / "execution_result.json")
            return
        route_geometry = load_route_geometry(PROJECT_ROOT, config, response.route_id)
        resolved = resolve_scene_spec(response, config, route_geometry)
        local_validation = {
            "status": "passed",
            "scene_spec_version": response.version,
            "scene_spec_sha256": canonical_json_sha256(response.as_dict()),
            "config_sha256": sha256_file(config_path),
            "route_geometry": {"route_id": route_geometry.route_id, "length_m": route_geometry.length_m},
            "resolved_scene": resolved.as_dict(),
            "api_call_made": bool(input_record["api_call_made"]),
            "api_provenance": input_record if bool(input_record["api_call_made"]) else None,
        }
        write_json(run_dir / "local_validation.json", local_validation)
        write_json(run_dir / "scene_spec.json", response.as_dict())
        write_json(run_dir / "resolved_scene.preflight.json", resolved.as_dict())
        if args.validate_only:
            update_metadata(metadata_path, state="complete", stage6_result="local_validation_only", validation_path="local_validation.json")
            print(run_dir / "local_validation.json")
            return

        weather_profile, weather_source_path = profile_from_config(PROJECT_ROOT, config, response.weather_id)
        calibration = load_json_object(calibration_path)
        verify_source_files(calibration_path, calibration)
        client = carla.Client(args.host, args.port)
        client.set_timeout(args.timeout)
        available_maps = list(client.get_available_maps())
        requested_map = str(config["map_name"])
        resolved_map_name = next(
            (name for name in available_maps if short_map_name(name).lower() == requested_map.lower()), None
        )
        if resolved_map_name is None:
            raise RuntimeError(f"{requested_map} is not available in the connected CARLA server")
        world = client.load_world(resolved_map_name, reset_settings=False, map_layers=carla.MapLayer.All)
        original_settings = configure_synchronous_world(world)
        map_ = world.get_map()
        if short_map_name(map_.name).lower() != requested_map.lower():
            raise RuntimeError(f"loaded {map_.name}, expected {requested_map}")
        road_line_operation = hide_road_lines(world)
        weather_record = apply_weather(world, response.weather_id, weather_profile)
        route_index = load_json_object(PROJECT_ROOT / str(config["approved_routes_run"]) / "revised_routes.json")
        route_item = next(
            (item for item in route_index["routes"] if isinstance(item, dict) and item.get("route_id") == response.route_id),
            None,
        )
        if route_item is None:
            raise RuntimeError("validated route is absent from the runtime route index")
        route = load_route(
            map_,
            PROJECT_ROOT / str(config["approved_routes_run"]) / str(route_item["path"]),
            requested_map,
            float(route_index["dense_step_m"]),
        )
        settings = config["short_validation"]
        assert isinstance(settings, dict)
        traffic_manager = client.get_trafficmanager(args.traffic_manager_port)
        traffic_manager.set_synchronous_mode(True)
        traffic_manager.set_random_device_seed(int(settings["traffic_manager_seed"]))
        library = world.get_blueprint_library()
        ego_blueprint = library.find(str(settings["ego_blueprint"]))
        ego = spawn_at_route_start(world, ego_blueprint, route)
        spawn_frame = world.tick()
        if world.get_snapshot().find(ego.id) is None:
            raise RuntimeError(f"ego vehicle is absent after spawn frame {spawn_frame}")
        live_checks = live_preflight(world, map_, library, resolved, ego)
        before = capture_observer_rgb(world, observer_transform(resolved.edits[0]), run_dir / "before_after" / "before.png")
        parked, actors = spawn_parked_vehicles(world, map_, library, resolved, ego)
        after = capture_observer_rgb(world, observer_transform(resolved.edits[0]), run_dir / "before_after" / "after.png")
        runtime_result = record_rig_and_drive(
            world,
            traffic_manager,
            args.traffic_manager_port,
            route,
            ego,
            parked,
            run_dir,
            calibration_path,
            calibration,
            config,
            args.sensor_timeout_s,
        )
        execution = {
            "status": "passed" if runtime_result["visibility_passed"] and all(runtime_result["route_check"]["checks"].values()) else "failed",
            "api_call_made": bool(input_record["api_call_made"]),
            "api_provenance": input_record if bool(input_record["api_call_made"]) else None,
            "map_name": map_.name,
            "carla_client_version": client.get_client_version(),
            "carla_server_version": client.get_server_version(),
            "weather": weather_record,
            "weather_source_config": weather_source_path.relative_to(PROJECT_ROOT).as_posix(),
            "road_line_operation": road_line_operation,
            "route": {"route_id": route.route_id, "length_m": route.length_m},
            "live_preflight": live_checks,
            "created_actors": actors,
            "before_after": {"before": before, "after": after},
            "camera_validation": runtime_result["camera_validation"],
            "visibility": runtime_result["visibility"],
            "per_sample_visibility": runtime_result["per_sample_visibility"],
            "visibility_passed": runtime_result["visibility_passed"],
            "route_check": runtime_result["route_check"],
            "timing": {
                "api_latency_s": input_record.get("api_latency_s"),
                "local_validation_and_resolution_s": input_record.get("local_validation_s"),
                "carla_application_and_validation_wall_s": time.monotonic() - started_wall,
            },
        }
        write_json(run_dir / "execution_result.json", execution)
        update_metadata(
            metadata_path,
            state="complete" if execution["status"] == "passed" else "failed",
            carla_client_version=client.get_client_version(),
            carla_server_version=client.get_server_version(),
            map_name=map_.name,
            stage6_result=execution["status"],
            validation_path="execution_result.json",
        )
        if execution["status"] != "passed":
            raise RuntimeError("Stage-6 local CARLA validation did not meet visibility or route checks")
        print(run_dir / "execution_result.json")
    except Exception as exc:
        failure = {"error_type": type(exc).__name__, "error": str(exc), "wall_duration_s": time.monotonic() - started_wall}
        write_json(run_dir / "execution_failure.json", failure)
        update_metadata(metadata_path, state="failed", stage6_error=str(exc), validation_path="execution_failure.json")
        raise
    finally:
        if ego is not None:
            ego.set_autopilot(False, args.traffic_manager_port)
        for actor in parked:
            actor.destroy()
        if ego is not None:
            ego.destroy()
        if traffic_manager is not None:
            traffic_manager.set_synchronous_mode(False)
        if world is not None and original_settings is not None:
            restore_world_settings(world, original_settings)


if __name__ == "__main__":
    main()
