#!/usr/bin/env python3
"""Recreate the stage-0 smoke view and test RoadLines hiding in that view.

This is a supplemental check for the old Town10HD_Opt smoke image.  It does
not change the selected Town01_Opt map for the project.  The original smoke
run did not record its vehicle spawn transform, so this script records the
reproduction method and the newly selected transform rather than claiming
pixel-identical replay.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import queue
from pathlib import Path

import carla

from stage1_map_api import (
    Capture,
    PNG_SIGNATURE,
    await_frame,
    compare_captures,
    configure_capture_settings,
    enum_number,
    restore_capture_settings,
    save_image,
    semantic_statistics,
    transform_to_dict,
    update_metadata,
)


REFERENCE_RUN = "20260916T210617Z-carla-smoke-beb230"
REFERENCE_IMAGE = Path("runs") / REFERENCE_RUN / "rgb" / "front.png"


def capture_vehicle_view(
    world: carla.World,
    vehicle: carla.Actor,
    destination: Path,
    run_dir: Path,
    timeout: float,
    road_line_id: int | None,
) -> Capture:
    rgb_queue: queue.Queue[carla.Image] = queue.Queue()
    semantic_queue: queue.Queue[carla.Image] = queue.Queue()
    rgb = semantic = None
    camera_relative = carla.Transform(carla.Location(x=1.6, z=2.3))
    try:
        rgb_bp = world.get_blueprint_library().find("sensor.camera.rgb")
        semantic_bp = world.get_blueprint_library().find("sensor.camera.semantic_segmentation")
        for blueprint in (rgb_bp, semantic_bp):
            blueprint.set_attribute("image_size_x", "800")
            blueprint.set_attribute("image_size_y", "600")
            blueprint.set_attribute("fov", "90")
            blueprint.set_attribute("sensor_tick", "0.0")
        rgb = world.spawn_actor(rgb_bp, camera_relative, attach_to=vehicle)
        semantic = world.spawn_actor(semantic_bp, camera_relative, attach_to=vehicle)
        rgb.listen(rgb_queue.put)
        semantic.listen(semantic_queue.put)
        frame = world.tick()
        rgb_image = await_frame(rgb_queue, frame, timeout)
        semantic_image = await_frame(semantic_queue, frame, timeout)
        rgb_raw = bytes(rgb_image.raw_data)
        semantic_raw = bytes(semantic_image.raw_data)
        save_image(rgb_image, destination / "rgb.png")
        save_image(semantic_image, destination / "semantic_raw.png")
        save_image(semantic_image, destination / "semantic_cityscapes.png", carla.ColorConverter.CityScapesPalette)
        return Capture(
            metadata={
                "frame": int(frame),
                "timestamp": float(rgb_image.timestamp),
                "resolution": {"width": int(rgb_image.width), "height": int(rgb_image.height)},
                "vehicle_transform": transform_to_dict(vehicle.get_transform()),
                "camera_relative_transform": transform_to_dict(camera_relative),
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
            },
            rgb_raw=rgb_raw,
            semantic_raw=semantic_raw,
        )
    finally:
        for actor in (rgb, semantic):
            if actor is not None:
                actor.stop()
                actor.destroy()


def image_has_png_signature(path: Path) -> bool:
    return path.is_file() and path.read_bytes()[:8] == PNG_SIGNATURE


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--map", default="Town10HD_Opt")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=2000, type=int)
    parser.add_argument("--timeout", default=45.0, type=float)
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.is_file():
        raise SystemExit(f"run directory was not created by create_run.py: {run_dir}")
    if not REFERENCE_IMAGE.is_file():
        raise SystemExit(f"missing reference image: {REFERENCE_IMAGE}")

    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout)
    vehicle = None
    world = client.load_world(args.map, reset_settings=False, map_layers=carla.MapLayer.All)
    original_settings = configure_capture_settings(world)
    try:
        actual_map = world.get_map().name
        road_line_label = getattr(carla.CityObjectLabel, "RoadLines", None)
        road_line_id = enum_number(road_line_label) if road_line_label is not None else None
        road_lines = list(world.get_environment_objects(road_line_label)) if road_line_label is not None else []
        vehicle_blueprint = next(iter(world.get_blueprint_library().filter("vehicle.*")), None)
        if vehicle_blueprint is None:
            raise RuntimeError("no vehicle blueprint is available")
        spawn_points = world.get_map().get_spawn_points()
        if not spawn_points:
            raise RuntimeError("map has no vehicle spawn points")
        selected_spawn_index = None
        for index, transform in enumerate(spawn_points):
            vehicle = world.try_spawn_actor(vehicle_blueprint, transform)
            if vehicle is not None:
                selected_spawn_index = index
                break
        if vehicle is None or selected_spawn_index is None:
            raise RuntimeError("could not reserve any map spawn point")

        before = capture_vehicle_view(
            world, vehicle, run_dir / "snapshots" / "town10hd_opt_reference" / "before", run_dir,
            args.timeout, road_line_id,
        )
        if road_lines:
            world.enable_environment_objects({int(item.id) for item in road_lines}, False)
            for _ in range(3):
                world.tick()
        after = capture_vehicle_view(
            world, vehicle, run_dir / "snapshots" / "town10hd_opt_reference" / "after_roadlines", run_dir,
            args.timeout, road_line_id,
        )
        comparison = compare_captures(before, after, road_line_id)
        paths = [
            before.metadata["rgb"]["path"], before.metadata["semantic"]["raw_path"],
            before.metadata["semantic"]["preview_path"], after.metadata["rgb"]["path"],
            after.metadata["semantic"]["raw_path"], after.metadata["semantic"]["preview_path"],
        ]
        assert all(isinstance(path, str) for path in paths)
        invalid_paths = [path for path in paths if not image_has_png_signature(run_dir / path)]
        result = {
            "schema_version": 1,
            "scope": "Supplemental Town10HD_Opt check of the stage-0 smoke view; not Town01_Opt acceptance evidence.",
            "reference": {
                "run_id": REFERENCE_RUN,
                "image": REFERENCE_IMAGE.as_posix(),
                "map": "Carla/Maps/Town10HD_Opt",
                "original_vehicle_transform_recorded": False,
                "reproduction_method": "same first-free-spawn loop, first vehicle blueprint, 800x600 90-degree front camera at x=1.6,z=2.3",
            },
            "requested_map": args.map,
            "actual_map": actual_map,
            "road_lines": {
                "semantic_id": road_line_id,
                "object_count": len(road_lines),
                "operation": "World.enable_environment_objects(RoadLines_ids, False)",
            },
            "selected_spawn_index": selected_spawn_index,
            "before": before.metadata,
            "after": after.metadata,
            "comparison": comparison,
            "validation": {
                "all_images_have_png_signature": not invalid_paths,
                "road_lines_present_before": comparison.get("road_lines_pixel_count_before", 0) > 0,
                "road_lines_absent_after": comparison.get("road_lines_pixel_count_after") == 0,
                "rgb_changed": comparison.get("rgb_changed_byte_fraction", 0) > 0,
                "missing_or_invalid_png_paths": invalid_paths,
            },
        }
        result["validation"]["status"] = "passed" if (
            result["validation"]["all_images_have_png_signature"]
            and result["validation"]["road_lines_present_before"]
            and result["validation"]["road_lines_absent_after"]
            and result["validation"]["rgb_changed"]
        ) else "failed"
        (run_dir / "reference_marking_probe.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        update_metadata(
            metadata_path,
            carla_client_version=client.get_client_version(),
            carla_server_version=client.get_server_version(),
            map_name=actual_map,
            reference_marking_probe={
                "path": "reference_marking_probe.json",
                "validation_status": result["validation"]["status"],
                "scope": result["scope"],
            },
            state="running",
        )
        print(run_dir / "reference_marking_probe.json")
    except Exception as exc:
        update_metadata(metadata_path, state="failed", reference_marking_probe_error=str(exc))
        raise
    finally:
        if vehicle is not None:
            vehicle.destroy()
        restore_capture_settings(world, original_settings)


if __name__ == "__main__":
    main()
