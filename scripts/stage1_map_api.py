#!/usr/bin/env python3
"""Probe CARLA 0.9.16 map/API capabilities for stage 1.

The script is deliberately a capability probe, rather than a dataset recorder.
It loads the required Town01 map, saves paired RGB/raw-semantic observations at
fixed locations, tests the documented RoadLines environment-object operation,
and records exactly what the installed server exposes.  It never edits Unreal
assets or OpenDRIVE.  All actors created by this script are destroyed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import queue
import re
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import carla


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ENVIRONMENT_LABEL_NAMES = (
    "Buildings",
    "Fences",
    "Other",
    "Pedestrians",
    "Poles",
    "RoadLines",
    "Roads",
    "Sidewalks",
    "Vegetation",
    "Vehicles",
    "Walls",
    "TrafficSigns",
    "Sky",
    "Ground",
    "Bridge",
    "RailTrack",
    "GuardRail",
    "TrafficLight",
    "Static",
    "Dynamic",
    "Water",
    "Terrain",
)
WEATHER_FIELDS = (
    "cloudiness",
    "precipitation",
    "precipitation_deposits",
    "wind_intensity",
    "sun_azimuth_angle",
    "sun_altitude_angle",
    "fog_density",
    "fog_distance",
    "wetness",
    "fog_falloff",
    "scattering_intensity",
    "mie_scattering_scale",
    "rayleigh_scattering_scale",
    "dust_storm",
)
ANIMAL_BLUEPRINT_PATTERN = re.compile(
    r"(?:^|[._-])(animal|dog|cat|deer|horse|cow|sheep|goat|pig|bird|bear|wolf|fox)(?:$|[._-])",
    re.IGNORECASE,
)


@dataclass
class Capture:
    metadata: dict[str, Any]
    rgb_raw: bytes
    semantic_raw: bytes


def update_metadata(path: Path, **values: object) -> None:
    metadata = json.loads(path.read_text())
    metadata.update(values)
    path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")


def enum_number(value: object) -> int | None:
    """Return a pybind enum's numeric value across CARLA wheel variants."""
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raw = getattr(value, "value", None)
        return int(raw) if raw is not None else None


def short_map_name(map_name: str) -> str:
    return map_name.rstrip("/").rsplit("/", 1)[-1]


def resolve_map(available_maps: list[str], requested: str) -> str | None:
    requested_lower = requested.lower()
    for map_name in available_maps:
        if short_map_name(map_name).lower() == requested_lower:
            return map_name
    return None


def weather_as_dict(weather: carla.WeatherParameters) -> dict[str, float]:
    return {
        field: float(getattr(weather, field))
        for field in WEATHER_FIELDS
        if hasattr(weather, field)
    }


def object_summary(environment_object: object) -> dict[str, object]:
    result: dict[str, object] = {"id": int(getattr(environment_object, "id"))}
    for field in ("name", "type"):
        value = getattr(environment_object, field, None)
        if value is not None:
            result[field] = str(value)
    transform = getattr(environment_object, "transform", None)
    if transform is not None:
        result["location"] = transform_to_dict(transform)["location"]
    return result


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


def topology_summary(map_: carla.Map) -> dict[str, int]:
    topology = map_.get_topology()
    return {"edge_count": len(topology), "waypoint_pair_count": len(topology)}


def find_capture_spots(world: carla.World) -> tuple[list[dict[str, object]], list[str]]:
    """Choose locations covering an ordinary lane, junction, and crosswalk/control.

    The map API has no portable stop-line query.  Crosswalk points are preferred;
    a traffic-light location is an explicitly labelled fallback rather than a
    claim that it contains a visible stop line.
    """
    map_ = world.get_map()
    warnings: list[str] = []
    waypoints = map_.generate_waypoints(2.0)
    driving_waypoints = [waypoint for waypoint in waypoints if waypoint.lane_type == carla.LaneType.Driving]
    if not driving_waypoints:
        raise RuntimeError("Town01 generated no driving waypoints")

    def spot(name: str, location: carla.Location, source: str) -> dict[str, object]:
        waypoint = map_.get_waypoint(location, project_to_road=True, lane_type=carla.LaneType.Driving)
        if waypoint is None:
            raise RuntimeError(f"could not project {name} location to a driving waypoint")
        return {
            "name": name,
            "source": source,
            "location": {
                "x": float(location.x),
                "y": float(location.y),
                "z": float(location.z),
            },
            "nearest_waypoint": {
                "road_id": int(waypoint.road_id),
                "section_id": int(waypoint.section_id),
                "lane_id": int(waypoint.lane_id),
                "s": float(waypoint.s),
                "is_junction": bool(waypoint.is_junction),
            },
        }

    straight = next((waypoint for waypoint in driving_waypoints if not waypoint.is_junction), None)
    junction = next((waypoint for waypoint in driving_waypoints if waypoint.is_junction), None)
    if straight is None:
        straight = driving_waypoints[0]
        warnings.append("No non-junction driving waypoint was found; the straight-road capture is a fallback.")
    if junction is None:
        junction = driving_waypoints[0]
        warnings.append("No junction driving waypoint was found; the intersection capture is a fallback.")

    selected = [
        spot("straight_road", straight.transform.location, "generated driving waypoint"),
        spot("intersection", junction.transform.location, "generated junction waypoint"),
    ]

    crosswalk_locations: list[carla.Location] = []
    try:
        crosswalk_locations = list(map_.get_crosswalks())
    except (AttributeError, RuntimeError) as exc:
        warnings.append(f"Map.get_crosswalks was unavailable: {exc}")
    if crosswalk_locations:
        selected.append(spot("crosswalk", crosswalk_locations[0], "Map.get_crosswalks()[0]"))
    else:
        traffic_lights = list(world.get_actors().filter("traffic.traffic_light*"))
        if traffic_lights:
            selected.append(spot("traffic_control", traffic_lights[0].get_location(), "first traffic.traffic_light actor"))
            warnings.append("No crosswalk API point was returned; captured a traffic-control location instead.")
        else:
            warnings.append("No crosswalk or traffic-light location was available for a third road-marking observation.")
    return selected, warnings


def camera_transform(spot: dict[str, object]) -> carla.Transform:
    location = spot["location"]
    assert isinstance(location, dict)
    # A 30 m nadir view with 90-degree horizontal FOV observes roughly a 60 m
    # road patch, including lane lines and nearby crossings without a vehicle.
    return carla.Transform(
        carla.Location(x=float(location["x"]), y=float(location["y"]), z=float(location["z"]) + 30.0),
        carla.Rotation(pitch=-90.0),
    )


def await_frame(images: queue.Queue[carla.Image], expected_frame: int, timeout: float) -> carla.Image:
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"timed out waiting for sensor frame {expected_frame}")
        image = images.get(timeout=remaining)
        if image.frame == expected_frame:
            return image
        if image.frame > expected_frame:
            raise RuntimeError(f"sensor skipped expected frame {expected_frame} and delivered {image.frame}")


def semantic_statistics(raw_data: bytes, road_line_id: int | None) -> dict[str, object]:
    # CARLA semantic cameras expose BGRA pixels; the raw tag is in the R byte.
    labels = raw_data[2::4]
    counts = Counter(labels)
    result: dict[str, object] = {
        "channel": "R in CARLA BGRA raw buffer",
        "unique_ids": sorted(int(label) for label in counts),
        "pixel_counts": {str(label): int(counts[label]) for label in sorted(counts)},
    }
    if road_line_id is not None:
        result["road_lines_id"] = road_line_id
        result["road_lines_pixel_count"] = int(counts.get(road_line_id, 0))
    return result


def save_image(image: carla.Image, path: Path, converter: carla.ColorConverter | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if converter is None:
        image.save_to_disk(str(path))
    else:
        image.save_to_disk(str(path), converter)
    if path.read_bytes()[:8] != PNG_SIGNATURE:
        raise RuntimeError(f"CARLA did not save a PNG at {path}")


def capture_pair(
    world: carla.World,
    spot: dict[str, object],
    destination: Path,
    run_dir: Path,
    width: int,
    height: int,
    timeout: float,
    road_line_id: int | None,
) -> Capture:
    rgb_queue: queue.Queue[carla.Image] = queue.Queue()
    semantic_queue: queue.Queue[carla.Image] = queue.Queue()
    rgb = semantic = None
    try:
        rgb_bp = world.get_blueprint_library().find("sensor.camera.rgb")
        semantic_bp = world.get_blueprint_library().find("sensor.camera.semantic_segmentation")
        for blueprint in (rgb_bp, semantic_bp):
            blueprint.set_attribute("image_size_x", str(width))
            blueprint.set_attribute("image_size_y", str(height))
            blueprint.set_attribute("fov", "90")
            blueprint.set_attribute("sensor_tick", "0.0")
        transform = camera_transform(spot)
        rgb = world.spawn_actor(rgb_bp, transform)
        semantic = world.spawn_actor(semantic_bp, transform)
        rgb.listen(rgb_queue.put)
        semantic.listen(semantic_queue.put)
        frame = world.tick()
        rgb_image = await_frame(rgb_queue, frame, timeout)
        semantic_image = await_frame(semantic_queue, frame, timeout)
        rgb_raw = bytes(rgb_image.raw_data)
        semantic_raw = bytes(semantic_image.raw_data)
        save_image(rgb_image, destination / "rgb.png")
        save_image(semantic_image, destination / "semantic_raw.png")
        # Conversion after writing semantic_raw preserves an unmodified raw-ID PNG.
        save_image(semantic_image, destination / "semantic_cityscapes.png", carla.ColorConverter.CityScapesPalette)
        metadata = {
            "spot": spot,
            "camera_transform": transform_to_dict(transform),
            "frame": int(frame),
            "timestamp": float(rgb_image.timestamp),
            "resolution": {"width": int(rgb_image.width), "height": int(rgb_image.height)},
            "rgb": {
                "path": (destination / "rgb.png").relative_to(run_dir).as_posix(),
                "raw_bgra_sha256": hashlib.sha256(rgb_raw).hexdigest(),
            },
            "semantic": {
                "raw_path": (destination / "semantic_raw.png").relative_to(run_dir).as_posix(),
                "preview_path": (destination / "semantic_cityscapes.png").relative_to(run_dir).as_posix(),
                "raw_bgra_sha256": hashlib.sha256(semantic_raw).hexdigest(),
                **semantic_statistics(semantic_raw, road_line_id),
            },
        }
        return Capture(metadata=metadata, rgb_raw=rgb_raw, semantic_raw=semantic_raw)
    finally:
        for actor in (rgb, semantic):
            if actor is not None:
                actor.stop()
                actor.destroy()


def byte_change_fraction(before: bytes, after: bytes) -> float | None:
    if len(before) != len(after) or not before:
        return None
    return sum(left != right for left, right in zip(before, after)) / len(before)


def compare_captures(before: Capture, after: Capture, road_line_id: int | None) -> dict[str, object]:
    semantic_before = before.metadata["semantic"]
    semantic_after = after.metadata["semantic"]
    assert isinstance(semantic_before, dict) and isinstance(semantic_after, dict)
    result: dict[str, object] = {
        "rgb_changed_byte_fraction": byte_change_fraction(before.rgb_raw, after.rgb_raw),
        "semantic_changed_byte_fraction": byte_change_fraction(before.semantic_raw, after.semantic_raw),
    }
    if road_line_id is not None:
        result["road_lines_pixel_count_before"] = semantic_before.get("road_lines_pixel_count")
        result["road_lines_pixel_count_after"] = semantic_after.get("road_lines_pixel_count")
    return result


def catalogue_environment_objects(world: carla.World) -> dict[str, object]:
    categories: dict[str, object] = {}
    for label_name in ENVIRONMENT_LABEL_NAMES:
        label = getattr(carla.CityObjectLabel, label_name, None)
        if label is None:
            categories[label_name] = {"available_in_client": False}
            continue
        try:
            objects = list(world.get_environment_objects(label))
            object_ids = sorted(int(environment_object.id) for environment_object in objects)
            categories[label_name] = {
                "available_in_client": True,
                "label_id": enum_number(label),
                "count": len(object_ids),
                "ids_sha256": hashlib.sha256(",".join(map(str, object_ids)).encode()).hexdigest(),
                "samples": [object_summary(environment_object) for environment_object in objects[:10]],
            }
            if label_name == "RoadLines":
                categories[label_name]["all_ids"] = object_ids
        except RuntimeError as exc:
            categories[label_name] = {"available_in_client": True, "error": str(exc)}
    return categories


def actor_lifecycle_probe(world: carla.World) -> dict[str, object]:
    blueprint_library = world.get_blueprint_library()
    vehicle_blueprint = next((bp for bp in blueprint_library.filter("vehicle.*")), None)
    spawn_point = next(iter(world.get_map().get_spawn_points()), None)
    if vehicle_blueprint is None or spawn_point is None:
        return {"status": "not_run", "reason": "vehicle blueprint or spawn point unavailable"}
    actor = None
    try:
        actor = world.try_spawn_actor(vehicle_blueprint, spawn_point)
        if actor is None:
            return {"status": "not_run", "reason": "first spawn point was occupied"}
        result = {
            "status": "passed",
            "blueprint": vehicle_blueprint.id,
            "actor_id": int(actor.id),
            "is_alive_before_destroy": bool(actor.is_alive),
            "spawn_transform": transform_to_dict(spawn_point),
        }
        return result
    finally:
        if actor is not None:
            actor.destroy()


def blueprint_catalogue(world: carla.World) -> dict[str, object]:
    identifiers = sorted(blueprint.id for blueprint in world.get_blueprint_library())
    animal_candidates = [identifier for identifier in identifiers if ANIMAL_BLUEPRINT_PATTERN.search(identifier)]
    return {
        "blueprint_count": len(identifiers),
        "vehicle_blueprint_count": sum(identifier.startswith("vehicle.") for identifier in identifiers),
        "walker_blueprint_count": sum(identifier.startswith("walker.") for identifier in identifiers),
        "sensor_blueprint_count": sum(identifier.startswith("sensor.") for identifier in identifiers),
        "animal_candidate_pattern": ANIMAL_BLUEPRINT_PATTERN.pattern,
        "animal_candidate_ids": animal_candidates,
        "animal_candidate_count": len(animal_candidates),
        "sample_blueprints": identifiers[:30],
    }


def configure_capture_settings(world: carla.World) -> dict[str, object]:
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


def restore_capture_settings(world: carla.World, original: dict[str, object]) -> None:
    settings = world.get_settings()
    settings.synchronous_mode = bool(original["synchronous_mode"])
    settings.fixed_delta_seconds = original["fixed_delta_seconds"]
    settings.no_rendering_mode = bool(original["no_rendering_mode"])
    world.apply_settings(settings)


def map_probe(
    client: carla.Client,
    map_name: str,
    run_dir: Path,
    width: int,
    height: int,
    timeout: float,
    *,
    test_road_lines: bool,
) -> dict[str, object]:
    world = client.load_world(map_name, reset_settings=False)
    original_settings = configure_capture_settings(world)
    try:
        map_ = world.get_map()
        actual_map_name = map_.name
        environment = catalogue_environment_objects(world)
        road_lines = environment.get("RoadLines", {})
        assert isinstance(road_lines, dict)
        road_line_ids = list(road_lines.get("all_ids", []))
        road_line_label = getattr(carla.CityObjectLabel, "RoadLines", None)
        road_line_id = enum_number(road_line_label) if road_line_label is not None else None
        spots, spot_warnings = find_capture_spots(world)
        captures: dict[str, dict[str, Capture]] = {"before": {}, "after_roadlines": {}, "weather_changed": {}}
        for spot in spots:
            name = str(spot["name"])
            captures["before"][name] = capture_pair(
            world, spot, run_dir / "snapshots" / "town01" / "before" / name,
                run_dir, width, height, timeout, road_line_id,
            )

        original_weather = world.get_weather()
        changed_weather = world.get_weather()
        changed_weather.cloudiness = 80.0
        changed_weather.precipitation = 60.0
        changed_weather.precipitation_deposits = 80.0
        changed_weather.wetness = 100.0
        changed_weather.sun_altitude_angle = 15.0
        world.set_weather(changed_weather)
        for _ in range(3):
            world.tick()
        straight_spot = next(spot for spot in spots if spot["name"] == "straight_road")
        captures["weather_changed"]["straight_road"] = capture_pair(
            world, straight_spot, run_dir / "snapshots" / "town01" / "weather_changed" / "straight_road",
            run_dir, width, height, timeout, road_line_id,
        )
        world.set_weather(original_weather)
        for _ in range(3):
            world.tick()

        topology_before = topology_summary(map_)
        removal_operation: dict[str, object]
        if test_road_lines and road_line_ids:
            world.enable_environment_objects(set(road_line_ids), False)
            for _ in range(3):
                world.tick()
            removal_operation = {
                "method": "World.enable_environment_objects(ids, False)",
                "attempted": True,
                "target": "CityObjectLabel.RoadLines",
                "target_object_count": len(road_line_ids),
                "target_object_ids": road_line_ids,
            }
        elif test_road_lines:
            removal_operation = {
                "method": "World.enable_environment_objects(ids, False)",
                "attempted": False,
                "target": "CityObjectLabel.RoadLines",
                "reason": "The installed map returned no RoadLines environment-object IDs.",
            }
        else:
            removal_operation = {"attempted": False, "reason": "not requested"}

        if removal_operation.get("attempted"):
            for spot in spots:
                name = str(spot["name"])
                captures["after_roadlines"][name] = capture_pair(
                    world, spot, run_dir / "snapshots" / "town01" / "after_roadlines" / name,
                    run_dir, width, height, timeout, road_line_id,
                )
        topology_after = topology_summary(map_)
        waypoint_checks = []
        for spot in spots:
            location = spot["location"]
            assert isinstance(location, dict)
            waypoint = map_.get_waypoint(
                carla.Location(x=float(location["x"]), y=float(location["y"]), z=float(location["z"])),
                project_to_road=True,
                lane_type=carla.LaneType.Driving,
            )
            waypoint_checks.append({
                "spot": spot["name"],
                "available": waypoint is not None,
                "road_id": int(waypoint.road_id) if waypoint is not None else None,
                "lane_id": int(waypoint.lane_id) if waypoint is not None else None,
            })

        comparison: dict[str, object] = {}
        for name, before in captures["before"].items():
            after = captures["after_roadlines"].get(name)
            if after is not None:
                comparison[name] = compare_captures(before, after, road_line_id)
        weather_comparison = compare_captures(
            captures["before"]["straight_road"], captures["weather_changed"]["straight_road"], road_line_id,
        )
        return {
            "requested_map": map_name,
            "actual_map": actual_map_name,
            "topology_before": topology_before,
            "topology_after": topology_after,
            "topology_unchanged": topology_before == topology_after,
            "capture_spots": spots,
            "capture_spot_warnings": spot_warnings,
            "environment_objects": environment,
            "road_line_semantic_id": road_line_id,
            "road_line_operation": removal_operation,
            "actor_lifecycle": actor_lifecycle_probe(world),
            "blueprints": blueprint_catalogue(world),
            "weather": {
                "baseline": weather_as_dict(original_weather),
                "changed": weather_as_dict(changed_weather),
                "straight_road_comparison": weather_comparison,
            },
            "navigation_checks_after_operation": waypoint_checks,
            "road_line_comparisons": comparison,
            "captures": {
                phase: {name: capture.metadata for name, capture in by_name.items()}
                for phase, by_name in captures.items()
            },
        }
    finally:
        restore_capture_settings(world, original_settings)


def opt_layer_probe(
    client: carla.Client,
    map_name: str,
    run_dir: Path,
    width: int,
    height: int,
    timeout: float,
) -> dict[str, object]:
    """Test Decals only on a confirmed `_Opt` map, isolated from Town01 evidence."""
    world = client.load_world(map_name, reset_settings=False, map_layers=carla.MapLayer.All)
    original_settings = configure_capture_settings(world)
    try:
        if not hasattr(world, "unload_map_layer") or not hasattr(carla.MapLayer, "Decals"):
            return {
                "requested_map": map_name,
                "actual_map": world.get_map().name,
                "decals_test": {"attempted": False, "reason": "Map-layer API or Decals enum unavailable in the installed client."},
            }
        road_line_label = getattr(carla.CityObjectLabel, "RoadLines", None)
        road_line_id = enum_number(road_line_label) if road_line_label is not None else None
        spots, warnings = find_capture_spots(world)
        straight_spot = next(spot for spot in spots if spot["name"] == "straight_road")
        before = capture_pair(
            world, straight_spot, run_dir / "snapshots" / "town01_opt" / "before_decals" / "straight_road",
            run_dir, width, height, timeout, road_line_id,
        )
        world.unload_map_layer(carla.MapLayer.Decals)
        for _ in range(3):
            world.tick()
        after = capture_pair(
            world, straight_spot, run_dir / "snapshots" / "town01_opt" / "after_decals" / "straight_road",
            run_dir, width, height, timeout, road_line_id,
        )
        # Restore Decals before testing the distinct direct-object operation.
        world.load_map_layer(carla.MapLayer.Decals)
        for _ in range(3):
            world.tick()
        road_line_objects = list(world.get_environment_objects(road_line_label)) if road_line_label is not None else []
        road_line_ids = {int(environment_object.id) for environment_object in road_line_objects}
        direct_hide: dict[str, object]
        if road_line_ids:
            world.enable_environment_objects(road_line_ids, False)
            for _ in range(3):
                world.tick()
            after_roadlines = capture_pair(
                world, straight_spot, run_dir / "snapshots" / "town01_opt" / "after_roadlines" / "straight_road",
                run_dir, width, height, timeout, road_line_id,
            )
            direct_hide = {
                "attempted": True,
                "method": "World.enable_environment_objects(ids, False)",
                "object_count": len(road_line_ids),
                "comparison_with_before": compare_captures(before, after_roadlines, road_line_id),
                "after": after_roadlines.metadata,
            }
        else:
            direct_hide = {
                "attempted": False,
                "reason": "Town01_Opt returned no RoadLines environment-object IDs.",
            }
        return {
            "requested_map": map_name,
            "actual_map": world.get_map().name,
            "capture_spot_warnings": warnings,
            "decals_test": {
                "attempted": True,
                "method": "World.unload_map_layer(MapLayer.Decals)",
                "straight_road_comparison": compare_captures(before, after, None),
                "before": before.metadata,
                "after": after.metadata,
            },
            "road_lines_direct_hide_test": direct_hide,
        }
    finally:
        restore_capture_settings(world, original_settings)


def opt_direct_road_lines_probe(
    client: carla.Client,
    map_name: str,
    run_dir: Path,
    width: int,
    height: int,
    timeout: float,
) -> dict[str, object]:
    """Test RoadLines hiding on Town01_Opt without changing any map layer."""
    world = client.load_world(map_name, reset_settings=False, map_layers=carla.MapLayer.All)
    original_settings = configure_capture_settings(world)
    try:
        road_line_label = getattr(carla.CityObjectLabel, "RoadLines", None)
        road_line_id = enum_number(road_line_label) if road_line_label is not None else None
        road_line_objects = list(world.get_environment_objects(road_line_label)) if road_line_label is not None else []
        spots, warnings = find_capture_spots(world)
        before = {
            str(spot["name"]): capture_pair(
                world, spot, run_dir / "snapshots" / "town01_opt_direct" / "before" / str(spot["name"]),
                run_dir, width, height, timeout, road_line_id,
            )
            for spot in spots
        }
        if road_line_objects:
            world.enable_environment_objects({int(item.id) for item in road_line_objects}, False)
            for _ in range(3):
                world.tick()
            after = {
                str(spot["name"]): capture_pair(
                    world, spot, run_dir / "snapshots" / "town01_opt_direct" / "after_roadlines" / str(spot["name"]),
                    run_dir, width, height, timeout, road_line_id,
                )
                for spot in spots
            }
            waypoint_checks = []
            for spot in spots:
                location = spot["location"]
                assert isinstance(location, dict)
                waypoint = world.get_map().get_waypoint(
                    carla.Location(x=float(location["x"]), y=float(location["y"]), z=float(location["z"])),
                    project_to_road=True,
                    lane_type=carla.LaneType.Driving,
                )
                waypoint_checks.append({
                    "spot": spot["name"],
                    "available": waypoint is not None,
                    "road_id": int(waypoint.road_id) if waypoint is not None else None,
                    "lane_id": int(waypoint.lane_id) if waypoint is not None else None,
                })
            direct_hide: dict[str, object] = {
                "attempted": True,
                "method": "World.enable_environment_objects(ids, False)",
                "object_count": len(road_line_objects),
                "captures_before": {name: capture.metadata for name, capture in before.items()},
                "captures_after": {name: capture.metadata for name, capture in after.items()},
                "comparisons": {
                    name: compare_captures(before[name], after[name], road_line_id)
                    for name in before
                },
                "navigation_waypoint_checks_after": waypoint_checks,
            }
        else:
            direct_hide = {
                "attempted": False,
                "reason": "Town01_Opt returned no RoadLines environment-object IDs.",
                "captures_before": {name: capture.metadata for name, capture in before.items()},
            }
        return {
            "requested_map": map_name,
            "actual_map": world.get_map().name,
            "capture_spot_warnings": warnings,
            "road_lines_semantic_id": road_line_id,
            "road_lines_direct_hide_test": direct_hide,
            "topology_after": topology_summary(world.get_map()),
        }
    finally:
        restore_capture_settings(world, original_settings)


def validate_probe(probe: dict[str, object], run_dir: Path) -> dict[str, object]:
    town01 = probe["town01"]
    assert isinstance(town01, dict)
    image_paths: list[str] = []
    captures = town01.get("captures", {})
    assert isinstance(captures, dict)
    for phase in captures.values():
        assert isinstance(phase, dict)
        for capture in phase.values():
            assert isinstance(capture, dict)
            rgb = capture.get("rgb", {})
            semantic = capture.get("semantic", {})
            assert isinstance(rgb, dict) and isinstance(semantic, dict)
            image_paths.extend([str(rgb["path"]), str(semantic["raw_path"]), str(semantic["preview_path"])])
    missing_or_invalid = [
        path for path in image_paths
        if not (run_dir / path).is_file() or (run_dir / path).read_bytes()[:8] != PNG_SIGNATURE
    ]
    lifecycle = town01.get("actor_lifecycle", {})
    assert isinstance(lifecycle, dict)
    weather = town01.get("weather", {})
    assert isinstance(weather, dict)
    weather_comparison = weather.get("straight_road_comparison", {})
    assert isinstance(weather_comparison, dict)
    return {
        "status": "passed" if not missing_or_invalid else "failed",
        "checks": {
            "town01_loaded": short_map_name(str(town01["actual_map"])).lower() == "town01",
            "paired_images_written": len(image_paths),
            "all_images_have_png_signature": not missing_or_invalid,
            "actor_lifecycle_passed": lifecycle.get("status") == "passed",
            "weather_render_changed": weather_comparison.get("rgb_changed_byte_fraction", 0) not in (None, 0),
            "topology_unchanged_after_road_line_operation": town01.get("topology_unchanged"),
            "navigation_waypoints_available_after_operation": all(
                check.get("available") for check in town01.get("navigation_checks_after_operation", [])
            ),
        },
        "missing_or_invalid_png_paths": missing_or_invalid,
        "road_marking_requirement": {
            "status": "requires_visual_assessment",
            "reason": "The raw semantic counts and identical-position captures are recorded, but full visible-line removal needs an explicit visual verdict across the saved coverage.",
        },
        "animal_availability": {
            "status": "catalogued_not_yet_asset_validated",
            "reason": "Blueprint-name candidates are recorded. A matching name alone is not evidence of a usable, visible, moving animal.",
        },
    }


def validate_opt_probe(probe: dict[str, object], run_dir: Path) -> dict[str, object]:
    """Validate file integrity for the isolated optional map-layer probe."""
    opt = probe["town01_opt"]
    assert isinstance(opt, dict)
    decals = opt.get("decals_test", {})
    assert isinstance(decals, dict)
    image_paths: list[str] = []
    for key in ("before", "after"):
        capture = decals.get(key)
        if not isinstance(capture, dict):
            continue
        rgb = capture.get("rgb", {})
        semantic = capture.get("semantic", {})
        assert isinstance(rgb, dict) and isinstance(semantic, dict)
        image_paths.extend([str(rgb["path"]), str(semantic["raw_path"]), str(semantic["preview_path"])])
    missing_or_invalid = [
        path for path in image_paths
        if not (run_dir / path).is_file() or (run_dir / path).read_bytes()[:8] != PNG_SIGNATURE
    ]
    return {
        "status": "passed" if decals.get("attempted") and not missing_or_invalid else "failed",
        "checks": {
            "town01_opt_loaded": short_map_name(str(opt.get("actual_map", ""))).lower() == "town01_opt",
            "decals_operation_attempted": decals.get("attempted") is True,
            "all_images_have_png_signature": not missing_or_invalid,
        },
        "missing_or_invalid_png_paths": missing_or_invalid,
        "scope": "This optional MapLayer.Decals experiment is separate from proof of the Town01 requirement.",
    }


def validate_opt_direct_probe(probe: dict[str, object], run_dir: Path) -> dict[str, object]:
    opt = probe["town01_opt"]
    assert isinstance(opt, dict)
    direct_hide = opt.get("road_lines_direct_hide_test", {})
    assert isinstance(direct_hide, dict)
    image_paths: list[str] = []
    for capture_set_key in ("captures_before", "captures_after"):
        capture_set = direct_hide.get(capture_set_key, {})
        if not isinstance(capture_set, dict):
            continue
        for capture in capture_set.values():
            assert isinstance(capture, dict)
            rgb = capture.get("rgb", {})
            semantic = capture.get("semantic", {})
            assert isinstance(rgb, dict) and isinstance(semantic, dict)
            image_paths.extend([str(rgb["path"]), str(semantic["raw_path"]), str(semantic["preview_path"])])
    invalid_paths = [
        path for path in image_paths
        if not (run_dir / path).is_file() or (run_dir / path).read_bytes()[:8] != PNG_SIGNATURE
    ]
    comparisons = direct_hide.get("comparisons", {})
    assert isinstance(comparisons, dict)
    semantic_counts_removed = bool(comparisons) and all(
        isinstance(comparison, dict)
        and comparison.get("road_lines_pixel_count_before", 0) > 0
        and comparison.get("road_lines_pixel_count_after") == 0
        for comparison in comparisons.values()
    )
    rgb_changed_at_all_spots = bool(comparisons) and all(
        isinstance(comparison, dict)
        and comparison.get("rgb_changed_byte_fraction", 0) > 0
        for comparison in comparisons.values()
    )
    navigation_checks = direct_hide.get("navigation_waypoint_checks_after", [])
    assert isinstance(navigation_checks, list)
    return {
        "status": "passed" if (
            direct_hide.get("attempted")
            and not invalid_paths
            and semantic_counts_removed
            and rgb_changed_at_all_spots
            and navigation_checks
            and all(check.get("available") for check in navigation_checks)
        ) else "failed",
        "checks": {
            "town01_opt_loaded": short_map_name(str(opt.get("actual_map", ""))).lower() == "town01_opt",
            "road_lines_direct_hide_attempted": direct_hide.get("attempted") is True,
            "all_images_have_png_signature": not invalid_paths,
            "road_lines_semantic_pixels_removed_at_all_spots": semantic_counts_removed,
            "rgb_changed_at_all_spots": rgb_changed_at_all_spots,
            "navigation_waypoints_available_after": bool(navigation_checks) and all(
                check.get("available") for check in navigation_checks
            ),
        },
        "missing_or_invalid_png_paths": invalid_paths,
        "scope": "This optional Town01_Opt probe is separate from proof of the required Town01 map.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=2000, type=int)
    parser.add_argument("--timeout", default=45.0, type=float)
    parser.add_argument("--width", default=800, type=int)
    parser.add_argument("--height", default=600, type=int)
    parser.add_argument(
        "--with-opt-layer-probe",
        action="store_true",
        help="Also run the optional Town01_Opt/Decals probe after the required Town01 probe.",
    )
    parser.add_argument(
        "--skip-opt-layer-probe",
        action="store_true",
        help="Deprecated compatibility flag; Town01_Opt is now opt-in.",
    )
    parser.add_argument(
        "--only-opt-layer-probe",
        action="store_true",
        help="Isolate Town01_Opt/Decals diagnostics in a separate run; does not test the required Town01 map.",
    )
    parser.add_argument(
        "--only-opt-direct-roadlines-probe",
        action="store_true",
        help="Isolate direct RoadLines hiding on Town01_Opt without changing Decals.",
    )
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.is_file():
        raise SystemExit(f"run directory was not created by create_run.py: {run_dir}")

    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout)
    try:
        available_maps = sorted(client.get_available_maps())
        town01_name = resolve_map(available_maps, "Town01")
        town01_opt_name = resolve_map(available_maps, "Town01_Opt")
        if town01_name is None:
            raise RuntimeError(f"Town01 was not returned by get_available_maps: {available_maps}")
        if args.only_opt_layer_probe or args.only_opt_direct_roadlines_probe:
            if town01_opt_name is None:
                raise RuntimeError("Town01_Opt was not returned by get_available_maps")
            if args.only_opt_direct_roadlines_probe:
                opt_probe = opt_direct_road_lines_probe(
                    client, town01_opt_name, run_dir, args.width, args.height, args.timeout,
                )
            else:
                opt_probe = opt_layer_probe(
                    client, town01_opt_name, run_dir, args.width, args.height, args.timeout,
                )
            probe = {
                "schema_version": 1,
                "carla_client_version": client.get_client_version(),
                "carla_server_version": client.get_server_version(),
                "available_maps": available_maps,
                "town01_available_name": town01_name,
                "town01_opt_available_name": town01_opt_name,
                "town01_opt": opt_probe,
            }
            validation = (
                validate_opt_direct_probe(probe, run_dir)
                if args.only_opt_direct_roadlines_probe else validate_opt_probe(probe, run_dir)
            )
            (run_dir / "map_api.json").write_text(json.dumps(probe, indent=2, sort_keys=True) + "\n")
            (run_dir / "validation.json").write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n")
            update_metadata(
                metadata_path,
                carla_client_version=probe["carla_client_version"],
                carla_server_version=probe["carla_server_version"],
                map_name=opt_probe.get("actual_map"),
                stage1_probe={
                    "path": "map_api.json",
                    "validation_path": "validation.json",
                    "validation_status": validation["status"],
                    "scope": (
                        "optional Town01_Opt direct RoadLines probe"
                        if args.only_opt_direct_roadlines_probe else "optional Town01_Opt Decals probe"
                    ),
                },
                state="running",
            )
            print(run_dir / "map_api.json")
            return
        town01 = map_probe(
            client, town01_name, run_dir, args.width, args.height, args.timeout, test_road_lines=True,
        )
        opt_probe: dict[str, object]
        if town01_opt_name is not None and args.with_opt_layer_probe and not args.skip_opt_layer_probe:
            opt_probe = opt_layer_probe(client, town01_opt_name, run_dir, args.width, args.height, args.timeout)
        else:
            opt_probe = {
                "attempted": False,
                "reason": "Town01_Opt unavailable" if town01_opt_name is None else "not requested (optional probe)",
            }
        probe = {
            "schema_version": 1,
            "carla_client_version": client.get_client_version(),
            "carla_server_version": client.get_server_version(),
            "available_maps": available_maps,
            "town01_available_name": town01_name,
            "town01_opt_available_name": town01_opt_name,
            "town01": town01,
            "town01_opt": opt_probe,
        }
        validation = validate_probe(probe, run_dir)
        (run_dir / "map_api.json").write_text(json.dumps(probe, indent=2, sort_keys=True) + "\n")
        (run_dir / "validation.json").write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n")
        update_metadata(
            metadata_path,
            carla_client_version=probe["carla_client_version"],
            carla_server_version=probe["carla_server_version"],
            map_name=town01["actual_map"],
            stage1_probe={
                "path": "map_api.json",
                "validation_path": "validation.json",
                "validation_status": validation["status"],
            },
            state="running",
        )
        print(run_dir / "map_api.json")
    except Exception as exc:
        update_metadata(metadata_path, state="failed", stage1_probe_error=str(exc))
        raise


if __name__ == "__main__":
    main()
