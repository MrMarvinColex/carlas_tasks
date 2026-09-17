#!/usr/bin/env python3
"""Isolated runtime-texture test for Town01 road-marking objects.

This is a follow-up to ``stage1_map_api.py``.  It tests the documented
``apply_color_texture_to_object`` API against actual Town01 RoadLines object
names, then combines it with the semantic-object hiding operation.  It does
not write Unreal assets and its changes live only in the running CARLA world.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import carla

import stage1_map_api as common


def solid_asphalt_texture() -> carla.TextureColor:
    texture = carla.TextureColor(2, 2)
    # A neutral asphalt-like colour is deliberately used only for this probe.
    # The test determines whether CARLA applies it to the target mesh at all.
    for x in range(2):
        for y in range(2):
            texture.set(x, y, carla.Color(117, 117, 117, 255))
    return texture


def target_spot(world: carla.World, target: object) -> dict[str, object]:
    transform = getattr(target, "transform")
    location = transform.location
    waypoint = world.get_map().get_waypoint(location, project_to_road=True, lane_type=carla.LaneType.Driving)
    if waypoint is None:
        raise RuntimeError(f"could not project RoadLines object {target.name} to a driving waypoint")
    return {
        "name": "target_road_marking",
        "source": f"RoadLines environment object {target.name}",
        "location": {"x": float(location.x), "y": float(location.y), "z": float(location.z)},
        "nearest_waypoint": {
            "road_id": int(waypoint.road_id),
            "section_id": int(waypoint.section_id),
            "lane_id": int(waypoint.lane_id),
            "s": float(waypoint.s),
            "is_junction": bool(waypoint.is_junction),
        },
    }


def texture_object_name(environment_name: str, material_names: set[str]) -> str | None:
    """Map a RoadLines environment-object name to texture API's material name.

    Town01 reports environment objects such as ``Road_Marking_Town01_1_SM_0``
    while ``get_names_of_all_objects`` exposes the corresponding material
    target as ``Road_Marking_Town01_1``.  The full name remains preferred to
    avoid applying a heuristic where it is not needed.
    """
    candidates = [environment_name, re.sub(r"_SM_\d+$", "", environment_name)]
    return next((candidate for candidate in candidates if candidate in material_names), None)


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
        maps = sorted(client.get_available_maps())
        town01_name = common.resolve_map(maps, "Town01")
        if town01_name is None:
            raise RuntimeError(f"Town01 was not returned by get_available_maps: {maps}")
        world = client.load_world(town01_name, reset_settings=False)
        original_settings = common.configure_capture_settings(world)
        try:
            road_line_label = getattr(carla.CityObjectLabel, "RoadLines", None)
            if road_line_label is None:
                raise RuntimeError("CityObjectLabel.RoadLines is missing in this client")
            road_line_id = common.enum_number(road_line_label)
            road_lines = list(world.get_environment_objects(road_line_label))
            if not road_lines:
                raise RuntimeError("Town01 returned no RoadLines environment objects")
            named_objects = set(world.get_names_of_all_objects())
            texture_names = {
                int(item.id): texture_object_name(str(item.name), named_objects)
                for item in road_lines
            }
            named_road_lines = [
                (item, texture_names[int(item.id)])
                for item in road_lines
                if texture_names[int(item.id)] is not None
            ]
            if not named_road_lines:
                raise RuntimeError("No Town01 RoadLines environment-object name is accepted by the texture API")
            target, target_texture_name = named_road_lines[0]
            assert target_texture_name is not None
            spot = target_spot(world, target)
            texture = solid_asphalt_texture()
            before = common.capture_pair(
                world, spot, run_dir / "snapshots" / "texture" / "before" / "target_road_marking",
                run_dir, args.width, args.height, args.timeout, road_line_id,
            )
            world.apply_color_texture_to_object(target_texture_name, carla.MaterialParameter.Diffuse, texture)
            for _ in range(3):
                world.tick()
            after_target_texture = common.capture_pair(
                world, spot, run_dir / "snapshots" / "texture" / "after_target_texture" / "target_road_marking",
                run_dir, args.width, args.height, args.timeout, road_line_id,
            )

            texture_errors: list[dict[str, str]] = []
            for item, material_name in named_road_lines:
                assert material_name is not None
                try:
                    world.apply_color_texture_to_object(material_name, carla.MaterialParameter.Diffuse, texture)
                except RuntimeError as exc:
                    texture_errors.append({"environment_name": item.name, "material_name": material_name, "error": str(exc)})
            world.enable_environment_objects({int(item.id) for item in road_lines}, False)
            for _ in range(3):
                world.tick()
            coverage_spots, coverage_warnings = common.find_capture_spots(world)
            after_combined = {}
            for coverage_spot in coverage_spots:
                name = str(coverage_spot["name"])
                after_combined[name] = common.capture_pair(
                    world, coverage_spot, run_dir / "snapshots" / "texture" / "after_texture_and_hide" / name,
                    run_dir, args.width, args.height, args.timeout, road_line_id,
                )
            topology_after = common.topology_summary(world.get_map())
        finally:
            common.restore_capture_settings(world, original_settings)

        probe = {
            "schema_version": 1,
            "carla_client_version": client.get_client_version(),
            "carla_server_version": client.get_server_version(),
            "requested_map": town01_name,
            "actual_map": world.get_map().name,
            "road_lines_semantic_id": road_line_id,
            "target": {"id": int(target.id), "environment_name": target.name, "material_name": target_texture_name, "spot": spot},
            "texture_operation": {
                "method": "World.apply_color_texture_to_object(name, MaterialParameter.Diffuse, TextureColor)",
                "texture_dimensions": {"width": texture.width, "height": texture.height},
                "texture_rgba": [117, 117, 117, 255],
                "target_before": before.metadata,
                "target_after": after_target_texture.metadata,
                "target_comparison": common.compare_captures(before, after_target_texture, road_line_id),
                "road_lines_total": len(road_lines),
                "road_lines_with_texture_name": len(named_road_lines),
                "road_lines_without_texture_name": [
                    {"id": int(item.id), "environment_name": item.name}
                    for item in road_lines
                    if texture_names[int(item.id)] is None
                ],
                "texture_errors": texture_errors,
            },
            "combined_operation": {
                "texture_applied_to_named_road_lines": len(named_road_lines),
                "hidden_road_line_object_ids": [int(item.id) for item in road_lines],
                "coverage_warnings": coverage_warnings,
                "captures": {name: capture.metadata for name, capture in after_combined.items()},
                "topology_after": topology_after,
            },
        }
        image_paths = []
        for capture in [before.metadata, after_target_texture.metadata, *(capture.metadata for capture in after_combined.values())]:
            rgb = capture["rgb"]
            semantic = capture["semantic"]
            assert isinstance(rgb, dict) and isinstance(semantic, dict)
            image_paths.extend([str(rgb["path"]), str(semantic["raw_path"]), str(semantic["preview_path"])])
        invalid_paths = [
            path for path in image_paths
            if not (run_dir / path).is_file() or (run_dir / path).read_bytes()[:8] != common.PNG_SIGNATURE
        ]
        validation = {
            "status": "passed" if not invalid_paths else "failed",
            "checks": {
                "town01_loaded": common.short_map_name(world.get_map().name).lower() == "town01",
                "texture_targeted_at_named_road_marking": True,
                "all_images_have_png_signature": not invalid_paths,
                "topology_after_combined_operation": topology_after,
            },
            "missing_or_invalid_png_paths": invalid_paths,
            "road_marking_requirement": {
                "status": "requires_visual_assessment",
                "reason": "The target texture and the combined hide+texture state are recorded; visible marking removal and road side effects require review of the saved RGB frames.",
            },
        }
        (run_dir / "texture_probe.json").write_text(json.dumps(probe, indent=2, sort_keys=True) + "\n")
        (run_dir / "validation.json").write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n")
        common.update_metadata(
            metadata_path,
            carla_client_version=probe["carla_client_version"],
            carla_server_version=probe["carla_server_version"],
            map_name=probe["actual_map"],
            stage1_texture_probe={"path": "texture_probe.json", "validation_path": "validation.json", "validation_status": validation["status"]},
            state="running",
        )
        print(run_dir / "texture_probe.json")
    except Exception as exc:
        common.update_metadata(metadata_path, state="failed", stage1_texture_probe_error=str(exc))
        raise


if __name__ == "__main__":
    main()
