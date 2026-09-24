#!/usr/bin/env python3
"""Strict Stage-7 passive SceneSpec for the one verified deer capability.

This module intentionally does not import CARLA.  A model can select no world
coordinates, controller, blueprint ID, animation, or traffic behaviour.  The
only accepted animal setup is the measured route-relative deer crossing from
the grounded AnimaSim probe.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from pathlib import Path
from typing import Any

from stage6_scene_spec import (
    RouteGeometry,
    RoutePoint,
    SceneSpecError,
    canonical_json_sha256,
    load_route_geometry,
    parse_json_document,
    route_pose_at_progress,
)


SCENE_SPEC_VERSION = "1.1"


def _expect_keys(value: dict[str, object], expected: set[str], path: str) -> None:
    missing, unexpected = sorted(expected - set(value)), sorted(set(value) - expected)
    if missing:
        raise SceneSpecError("missing_field", path, f"missing required field(s): {', '.join(missing)}")
    if unexpected:
        raise SceneSpecError("unexpected_field", path, f"unsupported field(s): {', '.join(unexpected)}")


def _string(value: object, path: str, maximum_length: int = 100) -> str:
    if not isinstance(value, str):
        raise SceneSpecError("wrong_type", path, "expected a string")
    if not value or len(value) > maximum_length:
        raise SceneSpecError("invalid_value", path, f"string length must be 1..{maximum_length}")
    return value


def _number(value: object, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SceneSpecError("wrong_type", path, "expected a finite JSON number")
    result = float(value)
    if not math.isfinite(result):
        raise SceneSpecError("invalid_value", path, "number must be finite")
    return result


def _integer(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SceneSpecError("wrong_type", path, "expected an integer")
    return value


def _same(value: float, expected: float, path: str) -> None:
    if not math.isclose(value, expected, rel_tol=0.0, abs_tol=1e-6):
        raise SceneSpecError("unsupported_value", path, f"only verified value {expected:g} is allowed")


def _short_map_name(value: str) -> str:
    return value.rstrip("/").rsplit("/", 1)[-1]


@dataclass(frozen=True)
class AnimalAnchor:
    route_progress_m: float


@dataclass(frozen=True)
class AnimalTrajectory:
    kind: str
    start_lateral_offset_m: float
    end_lateral_offset_m: float


@dataclass(frozen=True)
class AnimalEdit:
    type: str
    anchor: AnimalAnchor
    trajectory: AnimalTrajectory
    speed_mps: float
    start_time_s: float


@dataclass(frozen=True)
class AnimalSceneSpec:
    version: str
    map_name: str
    route_id: str
    weather_id: str
    seed: int
    animal: AnimalEdit

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ResolvedAnimalScene:
    spec: AnimalSceneSpec
    route: RouteGeometry
    blueprint_id: str
    semantic_class_id: int
    start_transform: RoutePoint
    end_transform: RoutePoint
    trajectory_yaw_deg: float

    def as_dict(self) -> dict[str, object]:
        def transform(point: RoutePoint, yaw_deg: float) -> dict[str, object]:
            return {
                "location": {"x": point.x, "y": point.y, "z": point.z},
                "rotation": {"roll": 0.0, "pitch": 0.0, "yaw": yaw_deg},
            }

        return {
            "scene_spec": self.spec.as_dict(),
            "route": {"route_id": self.route.route_id, "map_name": self.route.map_name, "length_m": self.route.length_m},
            "animal": {
                "blueprint_id": self.blueprint_id,
                "semantic_class_id": self.semantic_class_id,
                "start_transform": transform(self.start_transform, self.trajectory_yaw_deg),
                "end_transform": transform(self.end_transform, self.trajectory_yaw_deg),
                "trajectory_yaw_deg": self.trajectory_yaw_deg,
            },
        }


def parse_scene_spec_document(document: dict[str, object]) -> AnimalSceneSpec:
    _expect_keys(document, {"version", "map_name", "route_id", "weather_id", "seed", "animal"}, "$")
    version = _string(document["version"], "$.version")
    if version != SCENE_SPEC_VERSION:
        raise SceneSpecError("unsupported_version", "$.version", f"expected {SCENE_SPEC_VERSION!r}")
    animal = document["animal"]
    if not isinstance(animal, dict):
        raise SceneSpecError("wrong_type", "$.animal", "expected an object")
    _expect_keys(animal, {"type", "anchor", "trajectory", "speed_mps", "start_time_s"}, "$.animal")
    anchor = animal["anchor"]
    trajectory = animal["trajectory"]
    if not isinstance(anchor, dict) or not isinstance(trajectory, dict):
        raise SceneSpecError("wrong_type", "$.animal", "anchor and trajectory must be objects")
    _expect_keys(anchor, {"route_progress_m"}, "$.animal.anchor")
    _expect_keys(trajectory, {"kind", "start_lateral_offset_m", "end_lateral_offset_m"}, "$.animal.trajectory")
    return AnimalSceneSpec(
        version=version,
        map_name=_string(document["map_name"], "$.map_name"),
        route_id=_string(document["route_id"], "$.route_id"),
        weather_id=_string(document["weather_id"], "$.weather_id"),
        seed=_integer(document["seed"], "$.seed"),
        animal=AnimalEdit(
            type=_string(animal["type"], "$.animal.type"),
            anchor=AnimalAnchor(route_progress_m=_number(anchor["route_progress_m"], "$.animal.anchor.route_progress_m")),
            trajectory=AnimalTrajectory(
                kind=_string(trajectory["kind"], "$.animal.trajectory.kind"),
                start_lateral_offset_m=_number(trajectory["start_lateral_offset_m"], "$.animal.trajectory.start_lateral_offset_m"),
                end_lateral_offset_m=_number(trajectory["end_lateral_offset_m"], "$.animal.trajectory.end_lateral_offset_m"),
            ),
            speed_mps=_number(animal["speed_mps"], "$.animal.speed_mps"),
            start_time_s=_number(animal["start_time_s"], "$.animal.start_time_s"),
        ),
    )


def parse_scene_spec_json(text: str) -> AnimalSceneSpec:
    return parse_scene_spec_document(parse_json_document(text))


def load_stage7_config(path: Path) -> dict[str, object]:
    import json

    try:
        config = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise SceneSpecError("missing_file", str(path), "required configuration file does not exist") from exc
    except json.JSONDecodeError as exc:
        raise SceneSpecError("invalid_json", str(path), exc.msg) from exc
    if not isinstance(config, dict):
        raise SceneSpecError("wrong_type", str(path), "expected a JSON object")
    _expect_keys(
        config,
        {
            "schema_version", "scene_spec_version", "description", "map_name", "approved_routes_run",
            "weather_source_config", "allowed_route_ids", "allowed_weather_ids", "animal", "constraints",
        },
        str(path),
    )
    if config["schema_version"] != 1 or config["scene_spec_version"] != SCENE_SPEC_VERSION:
        raise SceneSpecError("unsupported_config", str(path), "unsupported Stage-7 configuration version")
    for key in ("allowed_route_ids", "allowed_weather_ids"):
        value = config[key]
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
            raise SceneSpecError("invalid_config", f"{path}.{key}", "expected a non-empty string list")
    if not isinstance(config["animal"], dict) or not isinstance(config["constraints"], dict):
        raise SceneSpecError("invalid_config", str(path), "animal and constraints must be objects")
    return config


def load_stage7_route(project_root: Path, config: dict[str, object], route_id: str) -> RouteGeometry:
    return load_route_geometry(project_root, config, route_id)


def resolve_scene_spec(spec: AnimalSceneSpec, config: dict[str, object], route: RouteGeometry) -> ResolvedAnimalScene:
    if spec.version != config["scene_spec_version"]:
        raise SceneSpecError("unsupported_version", "$.version", "does not match executor configuration")
    if _short_map_name(spec.map_name).lower() != str(config["map_name"]).lower():
        raise SceneSpecError("map_mismatch", "$.map_name", "only the configured map is allowed")
    if spec.route_id not in set(config["allowed_route_ids"]) or route.route_id != spec.route_id:
        raise SceneSpecError("unsupported_route", "$.route_id", "route is not enabled for this protocol")
    if spec.weather_id not in set(config["allowed_weather_ids"]):
        raise SceneSpecError("unsupported_weather", "$.weather_id", "weather is not allow-listed")
    constraints = config["constraints"]
    animal_config = config["animal"]
    assert isinstance(constraints, dict) and isinstance(animal_config, dict)
    if not 0 <= spec.seed <= _integer(constraints.get("maximum_seed"), "config.constraints.maximum_seed"):
        raise SceneSpecError("out_of_bounds", "$.seed", "seed is outside the configured range")
    if spec.animal.type != _string(animal_config.get("type"), "config.animal.type"):
        raise SceneSpecError("unsupported_animal", "$.animal.type", "only the verified deer is enabled")
    if spec.animal.trajectory.kind != _string(animal_config.get("trajectory_kind"), "config.animal.trajectory_kind"):
        raise SceneSpecError("unsupported_trajectory", "$.animal.trajectory.kind", "only the verified lateral crossing is enabled")
    _same(spec.animal.anchor.route_progress_m, _number(constraints.get("anchor_progress_m"), "config.constraints.anchor_progress_m"), "$.animal.anchor.route_progress_m")
    _same(spec.animal.trajectory.start_lateral_offset_m, _number(constraints.get("start_lateral_offset_m"), "config.constraints.start_lateral_offset_m"), "$.animal.trajectory.start_lateral_offset_m")
    _same(spec.animal.trajectory.end_lateral_offset_m, _number(constraints.get("end_lateral_offset_m"), "config.constraints.end_lateral_offset_m"), "$.animal.trajectory.end_lateral_offset_m")
    _same(spec.animal.speed_mps, _number(constraints.get("speed_mps"), "config.constraints.speed_mps"), "$.animal.speed_mps")
    _same(spec.animal.start_time_s, _number(constraints.get("start_time_s"), "config.constraints.start_time_s"), "$.animal.start_time_s")
    anchor = route_pose_at_progress(route, spec.animal.anchor.route_progress_m)
    heading = math.radians(anchor.yaw_deg)
    left_x, left_y = -math.sin(heading), math.cos(heading)
    start = RoutePoint(anchor.progress_m, anchor.x + spec.animal.trajectory.start_lateral_offset_m * left_x, anchor.y + spec.animal.trajectory.start_lateral_offset_m * left_y, anchor.z + _number(constraints.get("spawn_z_offset_m"), "config.constraints.spawn_z_offset_m"), anchor.yaw_deg)
    end = RoutePoint(anchor.progress_m, anchor.x + spec.animal.trajectory.end_lateral_offset_m * left_x, anchor.y + spec.animal.trajectory.end_lateral_offset_m * left_y, anchor.z + _number(constraints.get("spawn_z_offset_m"), "config.constraints.spawn_z_offset_m"), anchor.yaw_deg)
    trajectory_yaw = math.degrees(math.atan2(end.y - start.y, end.x - start.x))
    return ResolvedAnimalScene(
        spec=spec,
        route=route,
        blueprint_id=_string(animal_config.get("blueprint_id"), "config.animal.blueprint_id"),
        semantic_class_id=_integer(animal_config.get("semantic_class_id"), "config.animal.semantic_class_id"),
        start_transform=start,
        end_transform=end,
        trajectory_yaw_deg=trajectory_yaw,
    )


__all__ = [
    "AnimalSceneSpec", "ResolvedAnimalScene", "SCENE_SPEC_VERSION", "SceneSpecError", "canonical_json_sha256",
    "load_stage7_config", "load_stage7_route", "parse_scene_spec_json", "resolve_scene_spec",
]
