#!/usr/bin/env python3
"""Strict passive SceneSpec parsing and deterministic route-relative resolution.

This module intentionally has no API client and does not import CARLA.  It is
the boundary between an untrusted model response and the allow-listed runtime
executor in :mod:`stage6_local_scene`.  Successful specifications contain no
world coordinates and cannot carry executable code.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any


SCENE_SPEC_VERSION = "1.0"


class SceneSpecError(ValueError):
    """A deterministic, serializable parsing or validation failure."""

    def __init__(self, code: str, path: str, message: str) -> None:
        super().__init__(f"{code} at {path}: {message}")
        self.code = code
        self.path = path
        self.message = message

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


@dataclass(frozen=True)
class Anchor:
    route_progress_m: float
    side: str


@dataclass(frozen=True)
class SceneEdit:
    operation: str
    blueprint_id: str
    anchor: Anchor
    longitudinal_offset_m: float
    lateral_offset_m: float


@dataclass(frozen=True)
class SceneSpec:
    version: str
    map_name: str
    route_id: str
    weather_id: str
    seed: int
    edits: tuple[SceneEdit, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Refusal:
    version: str
    code: str
    requested_capabilities: tuple[str, ...]
    message: str

    def as_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "refusal": {
                "code": self.code,
                "requested_capabilities": list(self.requested_capabilities),
                "message": self.message,
            },
        }


@dataclass(frozen=True)
class RoutePoint:
    progress_m: float
    x: float
    y: float
    z: float
    yaw_deg: float


@dataclass(frozen=True)
class RouteGeometry:
    route_id: str
    map_name: str
    length_m: float
    points: tuple[RoutePoint, ...]


@dataclass(frozen=True)
class ResolvedEdit:
    edit_index: int
    operation: str
    blueprint_id: str
    anchor: Anchor
    longitudinal_offset_m: float
    lateral_offset_m: float
    target_progress_m: float
    x: float
    y: float
    z: float
    yaw_deg: float

    def as_dict(self) -> dict[str, object]:
        return {
            "edit_index": self.edit_index,
            "operation": self.operation,
            "blueprint_id": self.blueprint_id,
            "anchor": asdict(self.anchor),
            "longitudinal_offset_m": self.longitudinal_offset_m,
            "lateral_offset_m": self.lateral_offset_m,
            "target_progress_m": self.target_progress_m,
            "transform": {
                "location": {"x": self.x, "y": self.y, "z": self.z},
                "rotation": {"roll": 0.0, "pitch": 0.0, "yaw": self.yaw_deg},
            },
        }


@dataclass(frozen=True)
class ResolvedScene:
    spec: SceneSpec
    route: RouteGeometry
    edits: tuple[ResolvedEdit, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "scene_spec": self.spec.as_dict(),
            "route": {
                "route_id": self.route.route_id,
                "map_name": self.route.map_name,
                "length_m": self.route.length_m,
            },
            "resolved_edits": [edit.as_dict() for edit in self.edits],
        }


def _reject_constant(value: str) -> None:
    raise SceneSpecError("invalid_json_constant", "$", f"JSON constant {value!r} is not allowed")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise SceneSpecError("duplicate_key", "$", f"duplicate object key {key!r}")
        result[key] = value
    return result


def parse_json_document(text: str) -> dict[str, object]:
    """Parse one finite JSON object, rejecting duplicate keys and NaN/Infinity."""
    try:
        document = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except SceneSpecError:
        raise
    except json.JSONDecodeError as exc:
        raise SceneSpecError("invalid_json", "$", f"{exc.msg} at line {exc.lineno}, column {exc.colno}") from exc
    if not isinstance(document, dict):
        raise SceneSpecError("wrong_type", "$", "the top-level JSON value must be an object")
    return document


def _expect_keys(value: dict[str, object], expected: set[str], path: str) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing:
        raise SceneSpecError("missing_field", path, f"missing required field(s): {', '.join(missing)}")
    if unexpected:
        raise SceneSpecError("unexpected_field", path, f"unsupported field(s): {', '.join(unexpected)}")


def _string(value: object, path: str, *, maximum_length: int = 200) -> str:
    if not isinstance(value, str):
        raise SceneSpecError("wrong_type", path, "expected a string")
    if not value or len(value) > maximum_length:
        raise SceneSpecError("invalid_value", path, f"string length must be 1..{maximum_length}")
    return value


def _finite_number(value: object, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SceneSpecError("wrong_type", path, "expected a JSON number")
    number = float(value)
    if not math.isfinite(number):
        raise SceneSpecError("invalid_value", path, "number must be finite")
    return number


def _integer(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SceneSpecError("wrong_type", path, "expected an integer")
    return int(value)


def parse_scene_spec_document(document: dict[str, object]) -> SceneSpec:
    _expect_keys(document, {"version", "map_name", "route_id", "weather_id", "seed", "edits"}, "$")
    version = _string(document["version"], "$.version")
    if version != SCENE_SPEC_VERSION:
        raise SceneSpecError("unsupported_version", "$.version", f"expected {SCENE_SPEC_VERSION!r}")
    edits_value = document["edits"]
    if not isinstance(edits_value, list):
        raise SceneSpecError("wrong_type", "$.edits", "expected an array")
    edits: list[SceneEdit] = []
    for index, raw_edit in enumerate(edits_value):
        path = f"$.edits[{index}]"
        if not isinstance(raw_edit, dict):
            raise SceneSpecError("wrong_type", path, "expected an object")
        _expect_keys(raw_edit, {"operation", "blueprint_id", "anchor", "longitudinal_offset_m", "lateral_offset_m"}, path)
        raw_anchor = raw_edit["anchor"]
        if not isinstance(raw_anchor, dict):
            raise SceneSpecError("wrong_type", f"{path}.anchor", "expected an object")
        _expect_keys(raw_anchor, {"route_progress_m", "side"}, f"{path}.anchor")
        edits.append(
            SceneEdit(
                operation=_string(raw_edit["operation"], f"{path}.operation"),
                blueprint_id=_string(raw_edit["blueprint_id"], f"{path}.blueprint_id"),
                anchor=Anchor(
                    route_progress_m=_finite_number(raw_anchor["route_progress_m"], f"{path}.anchor.route_progress_m"),
                    side=_string(raw_anchor["side"], f"{path}.anchor.side", maximum_length=10),
                ),
                longitudinal_offset_m=_finite_number(raw_edit["longitudinal_offset_m"], f"{path}.longitudinal_offset_m"),
                lateral_offset_m=_finite_number(raw_edit["lateral_offset_m"], f"{path}.lateral_offset_m"),
            )
        )
    return SceneSpec(
        version=version,
        map_name=_string(document["map_name"], "$.map_name"),
        route_id=_string(document["route_id"], "$.route_id"),
        weather_id=_string(document["weather_id"], "$.weather_id"),
        seed=_integer(document["seed"], "$.seed"),
        edits=tuple(edits),
    )


def parse_refusal_document(document: dict[str, object]) -> Refusal:
    _expect_keys(document, {"version", "refusal"}, "$")
    version = _string(document["version"], "$.version")
    if version != SCENE_SPEC_VERSION:
        raise SceneSpecError("unsupported_version", "$.version", f"expected {SCENE_SPEC_VERSION!r}")
    refusal = document["refusal"]
    if not isinstance(refusal, dict):
        raise SceneSpecError("wrong_type", "$.refusal", "expected an object")
    _expect_keys(refusal, {"code", "requested_capabilities", "message"}, "$.refusal")
    code = _string(refusal["code"], "$.refusal.code", maximum_length=80)
    if code not in {"unsupported_capability", "impossible_request"}:
        raise SceneSpecError("invalid_value", "$.refusal.code", "unsupported refusal code")
    capabilities = refusal["requested_capabilities"]
    if not isinstance(capabilities, list) or not capabilities:
        raise SceneSpecError("wrong_type", "$.refusal.requested_capabilities", "expected a non-empty array")
    parsed_capabilities = tuple(
        _string(value, f"$.refusal.requested_capabilities[{index}]", maximum_length=80)
        for index, value in enumerate(capabilities)
    )
    if len(set(parsed_capabilities)) != len(parsed_capabilities):
        raise SceneSpecError("invalid_value", "$.refusal.requested_capabilities", "entries must be unique")
    return Refusal(
        version=version,
        code=code,
        requested_capabilities=parsed_capabilities,
        message=_string(refusal["message"], "$.refusal.message", maximum_length=500),
    )


def parse_response_json(text: str) -> SceneSpec | Refusal:
    """Parse either a SceneSpec or the documented structured refusal response."""
    document = parse_json_document(text)
    if "refusal" in document:
        return parse_refusal_document(document)
    return parse_scene_spec_document(document)


def parse_scene_spec_json(text: str) -> SceneSpec:
    parsed = parse_response_json(text)
    if isinstance(parsed, Refusal):
        raise SceneSpecError("refusal_not_scene", "$.refusal", "a refusal cannot be applied as a SceneSpec")
    return parsed


def _short_map_name(name: str) -> str:
    return name.rstrip("/").rsplit("/", 1)[-1]


def _load_json_object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise SceneSpecError("missing_file", str(path), "required configuration file does not exist") from exc
    except json.JSONDecodeError as exc:
        raise SceneSpecError("invalid_json", str(path), exc.msg) from exc
    if not isinstance(value, dict):
        raise SceneSpecError("wrong_type", str(path), "expected a JSON object")
    return value


def load_stage6_config(path: Path) -> dict[str, object]:
    config = _load_json_object(path)
    required = {
        "schema_version",
        "scene_spec_version",
        "description",
        "map_name",
        "approved_routes_run",
        "weather_source_config",
        "allowed_route_ids",
        "allowed_weather_ids",
        "allowed_vehicle_blueprints",
        "operations",
        "allowed_sides",
        "constraints",
        "short_validation",
    }
    _expect_keys(config, required, str(path))
    if config["schema_version"] != 1 or config["scene_spec_version"] != SCENE_SPEC_VERSION:
        raise SceneSpecError("unsupported_config", str(path), "unsupported Stage-6 configuration version")
    for key in ("allowed_route_ids", "allowed_weather_ids", "allowed_vehicle_blueprints", "operations", "allowed_sides"):
        value = config[key]
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
            raise SceneSpecError("invalid_config", f"{path}.{key}", "expected a non-empty string array")
    for key in ("constraints", "short_validation"):
        if not isinstance(config[key], dict):
            raise SceneSpecError("invalid_config", f"{path}.{key}", "expected an object")
    return config


def load_route_geometry(project_root: Path, config: dict[str, object], route_id: str) -> RouteGeometry:
    routes_run = project_root / str(config["approved_routes_run"])
    index = _load_json_object(routes_run / "revised_routes.json")
    routes = index.get("routes")
    if not isinstance(routes, list):
        raise SceneSpecError("invalid_route_index", str(routes_run / "revised_routes.json"), "routes must be an array")
    item = next((value for value in routes if isinstance(value, dict) and value.get("route_id") == route_id), None)
    if item is None:
        raise SceneSpecError("unknown_route", "$.route_id", f"route {route_id!r} is absent from the approved index")
    path_value = item.get("path")
    if not isinstance(path_value, str):
        raise SceneSpecError("invalid_route_index", str(routes_run), "route path is absent")
    document = _load_json_object(routes_run / path_value)
    if _short_map_name(str(document.get("map_name", ""))).lower() != str(config["map_name"]).lower():
        raise SceneSpecError("route_map_mismatch", str(routes_run / path_value), "route names another map")
    dense = document.get("dense_reference")
    if not isinstance(dense, dict) or not isinstance(dense.get("waypoints"), list):
        raise SceneSpecError("invalid_route", str(routes_run / path_value), "dense reference waypoints are absent")
    points: list[RoutePoint] = []
    progress = 0.0
    previous: RoutePoint | None = None
    for index_value, raw in enumerate(dense["waypoints"]):
        if not isinstance(raw, dict):
            raise SceneSpecError("invalid_route", str(routes_run / path_value), f"waypoint {index_value} is not an object")
        transform = raw.get("transform")
        if not isinstance(transform, dict):
            raise SceneSpecError("invalid_route", str(routes_run / path_value), f"waypoint {index_value} lacks transform")
        location, rotation = transform.get("location"), transform.get("rotation")
        if not isinstance(location, dict) or not isinstance(rotation, dict):
            raise SceneSpecError("invalid_route", str(routes_run / path_value), f"waypoint {index_value} has malformed transform")
        point = RoutePoint(
            progress_m=progress,
            x=_finite_number(location.get("x"), f"route[{index_value}].x"),
            y=_finite_number(location.get("y"), f"route[{index_value}].y"),
            z=_finite_number(location.get("z"), f"route[{index_value}].z"),
            yaw_deg=_finite_number(rotation.get("yaw"), f"route[{index_value}].yaw"),
        )
        if previous is not None:
            progress += math.hypot(point.x - previous.x, point.y - previous.y)
            point = RoutePoint(progress, point.x, point.y, point.z, point.yaw_deg)
        points.append(point)
        previous = point
    if len(points) < 10 or progress <= 0.0:
        raise SceneSpecError("invalid_route", str(routes_run / path_value), "route must have at least ten non-zero-length points")
    stored_length = _finite_number(document.get("length_m"), f"{routes_run / path_value}.length_m")
    if abs(stored_length - progress) > 0.25:
        raise SceneSpecError("invalid_route", str(routes_run / path_value), "stored and reconstructed length differ")
    return RouteGeometry(route_id=route_id, map_name=str(config["map_name"]), length_m=progress, points=tuple(points))


def _interpolate_angle_deg(first: float, second: float, fraction: float) -> float:
    delta = (second - first + 180.0) % 360.0 - 180.0
    return first + fraction * delta


def route_pose_at_progress(route: RouteGeometry, progress_m: float) -> RoutePoint:
    if progress_m < 0.0 or progress_m > route.length_m:
        raise SceneSpecError("invalid_value", "$.edits[].anchor.route_progress_m", "progress lies outside the route")
    for first, second in zip(route.points, route.points[1:]):
        if progress_m <= second.progress_m + 1e-9:
            span = second.progress_m - first.progress_m
            fraction = 0.0 if span == 0.0 else (progress_m - first.progress_m) / span
            return RoutePoint(
                progress_m=progress_m,
                x=first.x + fraction * (second.x - first.x),
                y=first.y + fraction * (second.y - first.y),
                z=first.z + fraction * (second.z - first.z),
                yaw_deg=_interpolate_angle_deg(first.yaw_deg, second.yaw_deg, fraction),
            )
    return route.points[-1]


def _config_number(config: dict[str, object], key: str) -> float:
    constraints = config["constraints"]
    assert isinstance(constraints, dict)
    return _finite_number(constraints.get(key), f"config.constraints.{key}")


def _config_range(config: dict[str, object], key: str) -> tuple[float, float]:
    constraints = config["constraints"]
    assert isinstance(constraints, dict)
    raw = constraints.get(key)
    if not isinstance(raw, list) or len(raw) != 2:
        raise SceneSpecError("invalid_config", f"config.constraints.{key}", "expected two-number array")
    lower, upper = (_finite_number(raw[0], f"config.constraints.{key}[0]"), _finite_number(raw[1], f"config.constraints.{key}[1]"))
    if lower > upper:
        raise SceneSpecError("invalid_config", f"config.constraints.{key}", "lower bound exceeds upper bound")
    return lower, upper


def _require_range(value: float, lower: float, upper: float, path: str) -> None:
    if value < lower or value > upper:
        raise SceneSpecError("out_of_bounds", path, f"value {value:g} must be within [{lower:g}, {upper:g}]")


def resolve_scene_spec(spec: SceneSpec, config: dict[str, object], route: RouteGeometry) -> ResolvedScene:
    """Validate policy constraints and resolve only route-relative coordinates.

    This is deliberately independent of the live simulator.  The executor adds
    the second validation layer against the actual CARLA map, actors, and
    blueprint library immediately before spawning anything.
    """
    if spec.version != str(config["scene_spec_version"]):
        raise SceneSpecError("unsupported_version", "$.version", "does not match executor configuration")
    if _short_map_name(spec.map_name).lower() != str(config["map_name"]).lower():
        raise SceneSpecError("map_mismatch", "$.map_name", "only the configured Town01_Opt base scene is allowed")
    allowed_routes = set(config["allowed_route_ids"])
    if spec.route_id not in allowed_routes:
        raise SceneSpecError("unsupported_route", "$.route_id", "route is not enabled for this protocol")
    if route.route_id != spec.route_id:
        raise SceneSpecError("route_mismatch", "$.route_id", "route geometry does not match the specification")
    if spec.weather_id not in set(config["allowed_weather_ids"]):
        raise SceneSpecError("unsupported_weather", "$.weather_id", "weather profile is not allow-listed")
    max_seed = int(_config_number(config, "maximum_seed"))
    _require_range(float(spec.seed), 0.0, float(max_seed), "$.seed")
    maximum_edits = int(_config_number(config, "maximum_edit_count"))
    if not 1 <= len(spec.edits) <= maximum_edits:
        raise SceneSpecError("out_of_bounds", "$.edits", f"must contain 1..{maximum_edits} edits")

    minimum_anchor = _config_number(config, "minimum_anchor_progress_m")
    edge_clearance = _config_number(config, "minimum_route_edge_clearance_m")
    longitudinal_bounds = _config_range(config, "longitudinal_offset_range_m")
    lateral_bounds = _config_range(config, "lateral_offset_range_m")
    spawn_z_offset = _config_number(config, "spawn_z_offset_m")
    allowed_operations = set(config["operations"])
    allowed_blueprints = set(config["allowed_vehicle_blueprints"])
    resolved: list[ResolvedEdit] = []
    for index, edit in enumerate(spec.edits):
        path = f"$.edits[{index}]"
        if edit.operation not in allowed_operations:
            raise SceneSpecError("unsupported_operation", f"{path}.operation", "operation is not allow-listed")
        if edit.blueprint_id not in allowed_blueprints:
            raise SceneSpecError("unsupported_blueprint", f"{path}.blueprint_id", "blueprint is not allow-listed")
        if edit.anchor.side not in set(config["allowed_sides"]):
            raise SceneSpecError("invalid_value", f"{path}.anchor.side", "side is not enabled for this route protocol")
        _require_range(edit.anchor.route_progress_m, minimum_anchor, route.length_m - edge_clearance, f"{path}.anchor.route_progress_m")
        _require_range(edit.longitudinal_offset_m, *longitudinal_bounds, f"{path}.longitudinal_offset_m")
        _require_range(edit.lateral_offset_m, *lateral_bounds, f"{path}.lateral_offset_m")
        target_progress = edit.anchor.route_progress_m + edit.longitudinal_offset_m
        _require_range(target_progress, edge_clearance, route.length_m - edge_clearance, f"{path}.longitudinal_offset_m")
        pose = route_pose_at_progress(route, edit.anchor.route_progress_m)
        heading_rad = math.radians(pose.yaw_deg)
        forward_x, forward_y = math.cos(heading_rad), math.sin(heading_rad)
        right_x, right_y = -math.sin(heading_rad), math.cos(heading_rad)
        side_multiplier = 1.0 if edit.anchor.side == "right" else -1.0
        resolved.append(
            ResolvedEdit(
                edit_index=index,
                operation=edit.operation,
                blueprint_id=edit.blueprint_id,
                anchor=edit.anchor,
                longitudinal_offset_m=edit.longitudinal_offset_m,
                lateral_offset_m=edit.lateral_offset_m,
                target_progress_m=target_progress,
                x=pose.x + forward_x * edit.longitudinal_offset_m + right_x * side_multiplier * edit.lateral_offset_m,
                y=pose.y + forward_y * edit.longitudinal_offset_m + right_y * side_multiplier * edit.lateral_offset_m,
                z=pose.z + spawn_z_offset,
                yaw_deg=pose.yaw_deg,
            )
        )
    minimum_ego_distance = _config_number(config, "minimum_ego_object_separation_m")
    minimum_object_distance = _config_number(config, "minimum_static_object_separation_m")
    start = route.points[0]
    for edit in resolved:
        if math.hypot(edit.x - start.x, edit.y - start.y) < minimum_ego_distance:
            raise SceneSpecError("spatial_conflict", f"$.edits[{edit.edit_index}]", "target is too close to the ego spawn")
    for index, first in enumerate(resolved):
        for second in resolved[index + 1 :]:
            if math.hypot(first.x - second.x, first.y - second.y) < minimum_object_distance:
                raise SceneSpecError("spatial_conflict", "$.edits", "two planned parked vehicles are too close")
    return ResolvedScene(spec=spec, route=route, edits=tuple(resolved))


def canonical_json_sha256(value: object) -> str:
    """Stable digest used to bind a resolved scene to its exact local input."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
