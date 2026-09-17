#!/usr/bin/env python3
"""Test CARLA's all-material texture API on one actual Town01 road marking.

This final stage-1 texture check complements the Diffuse-only probe.  It uses
``World.apply_textures_to_object`` with all supported texture channels and a
64x64 texture, then preserves an RGB/raw-semantic before/after pair.  It does
not edit OpenDRIVE, Unreal content, or files inside the CARLA image.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import carla

import stage1_map_api as common
from stage1_texture_probe import target_spot, texture_object_name


TEXTURE_SIZE = 64


def color_texture() -> carla.TextureColor:
    texture = carla.TextureColor(TEXTURE_SIZE, TEXTURE_SIZE)
    for x in range(TEXTURE_SIZE):
        for y in range(TEXTURE_SIZE):
            texture.set(x, y, carla.Color(117, 117, 117, 255))
    return texture


def float_texture(color: carla.FloatColor) -> carla.TextureFloatColor:
    texture = carla.TextureFloatColor(TEXTURE_SIZE, TEXTURE_SIZE)
    for x in range(TEXTURE_SIZE):
        for y in range(TEXTURE_SIZE):
            texture.set(x, y, color)
    return texture


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=2000, type=int)
    parser.add_argument("--timeout", default=45.0, type=float)
    parser.add_argument("--width", default=800, type=int)
    parser.add_argument("--height", default=600, type=int)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.is_file():
        raise SystemExit(f"run directory was not created by create_run.py: {run_dir}")

    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout)
    try:
        town01 = common.resolve_map(sorted(client.get_available_maps()), "Town01")
        if town01 is None:
            raise RuntimeError("Town01 was not returned by get_available_maps")
        world = client.load_world(town01, reset_settings=False)
        original_settings = common.configure_capture_settings(world)
        try:
            road_line_label = carla.CityObjectLabel.RoadLines
            road_line_id = common.enum_number(road_line_label)
            road_lines = list(world.get_environment_objects(road_line_label))
            material_names = set(world.get_names_of_all_objects())
            named = [
                (item, texture_object_name(str(item.name), material_names))
                for item in road_lines
            ]
            target, material_name = next((pair for pair in named if pair[1] is not None), (None, None))
            if target is None or material_name is None:
                raise RuntimeError("No RoadLines environment object resolved to an all-textures API name")
            spot = target_spot(world, target)
            before = common.capture_pair(
                world, spot, run_dir / "snapshots" / "full_texture" / "before" / "target_road_marking",
                run_dir, args.width, args.height, args.timeout, road_line_id,
            )
            diffuse = color_texture()
            emissive = float_texture(carla.FloatColor(0.0, 0.0, 0.0, 1.0))
            normal = float_texture(carla.FloatColor(0.5, 0.5, 1.0, 1.0))
            ao_roughness_metallic_emissive = float_texture(carla.FloatColor(1.0, 1.0, 0.0, 0.0))
            world.apply_textures_to_object(
                material_name, diffuse, emissive, normal, ao_roughness_metallic_emissive,
            )
            for _ in range(3):
                world.tick()
            after = common.capture_pair(
                world, spot, run_dir / "snapshots" / "full_texture" / "after" / "target_road_marking",
                run_dir, args.width, args.height, args.timeout, road_line_id,
            )
        finally:
            common.restore_capture_settings(world, original_settings)

        probe = {
            "schema_version": 1,
            "carla_client_version": client.get_client_version(),
            "carla_server_version": client.get_server_version(),
            "actual_map": world.get_map().name,
            "road_lines_semantic_id": road_line_id,
            "target": {
                "id": int(target.id),
                "environment_name": target.name,
                "material_name": material_name,
                "spot": spot,
            },
            "operation": {
                "method": "World.apply_textures_to_object",
                "texture_size": [TEXTURE_SIZE, TEXTURE_SIZE],
                "diffuse_rgba": [117, 117, 117, 255],
                "emissive_rgba_float": [0.0, 0.0, 0.0, 1.0],
                "normal_rgba_float": [0.5, 0.5, 1.0, 1.0],
                "ao_roughness_metallic_emissive_rgba_float": [1.0, 1.0, 0.0, 0.0],
                "before": before.metadata,
                "after": after.metadata,
                "comparison": common.compare_captures(before, after, road_line_id),
            },
        }
        image_paths = [
            str(before.metadata["rgb"]["path"]), str(before.metadata["semantic"]["raw_path"]), str(before.metadata["semantic"]["preview_path"]),
            str(after.metadata["rgb"]["path"]), str(after.metadata["semantic"]["raw_path"]), str(after.metadata["semantic"]["preview_path"]),
        ]
        invalid_paths = [
            path for path in image_paths
            if not (run_dir / path).is_file() or (run_dir / path).read_bytes()[:8] != common.PNG_SIGNATURE
        ]
        validation = {
            "status": "passed" if not invalid_paths else "failed",
            "checks": {
                "town01_loaded": common.short_map_name(world.get_map().name).lower() == "town01",
                "all_textures_applied_to_resolved_road_marking": True,
                "all_images_have_png_signature": not invalid_paths,
            },
            "missing_or_invalid_png_paths": invalid_paths,
            "road_marking_requirement": {
                "status": "requires_visual_assessment",
                "reason": "Only a paired capture can determine whether the all-textures API changes the visible marking.",
            },
        }
        (run_dir / "full_texture_probe.json").write_text(json.dumps(probe, indent=2, sort_keys=True) + "\n")
        (run_dir / "validation.json").write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n")
        common.update_metadata(
            metadata_path,
            carla_client_version=probe["carla_client_version"],
            carla_server_version=probe["carla_server_version"],
            map_name=probe["actual_map"],
            stage1_full_texture_probe={"path": "full_texture_probe.json", "validation_path": "validation.json", "validation_status": validation["status"]},
            state="running",
        )
        print(run_dir / "full_texture_probe.json")
    except Exception as exc:
        common.update_metadata(metadata_path, state="failed", stage1_full_texture_probe_error=str(exc))
        raise


if __name__ == "__main__":
    main()
