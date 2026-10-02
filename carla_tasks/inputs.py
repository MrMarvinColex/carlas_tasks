"""Validate portable experiment inputs without CARLA, a GPU, or historical runs.

Only declared dependencies are read. Provenance references identify evidence;
they never trigger traversal of ``runs/`` or dataset images.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .cameras import CAMERA_ORDER

DEFAULT_ROUTES_DIR = Path("inputs/routes/town01_opt_short_v1")
DEFAULT_CALIBRATION = Path("configs/av2/54bc6dbc-ebfb-3fba-b5b3-57f88b4b79ca/calibration.json")
DEFAULT_CONFIGS = tuple(Path("configs") / name for name in (
    "stage4_baseline_matrix.json", "stage6_scene_editing.json",
    "stage7_scene_editing.json", "stage7_animasim_probe.json",
))


class InputValidationError(ValueError):
    """A missing, corrupted, or inconsistent portable dependency."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InputValidationError(message)


def _number(value: object, label: str, *, positive: bool = False) -> float:
    _require(isinstance(value, (float, int)) and not isinstance(value, bool), f"{label}: expected a number")
    result = float(value)
    _require(math.isfinite(result) and (not positive or result > 0), f"{label}: invalid number")
    return result


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InputValidationError(f"cannot read JSON {path}: {exc}") from exc
    _require(isinstance(value, dict), f"{path}: expected a JSON object")
    _require(type(value.get("schema_version")) is int and value["schema_version"] == 1, f"{path}: unsupported schema_version")
    return value


def _within(root: Path, relative: object) -> Path:
    _require(isinstance(relative, (str, Path)) and bool(str(relative)), "dependency path is empty")
    path = Path(relative)
    _require(not path.is_absolute() and ".." not in path.parts, f"unsafe dependency path: {relative}")
    resolved_root = root.resolve()
    resolved = (resolved_root / path).resolve()
    _require(resolved.is_relative_to(resolved_root), f"dependency escapes its root: {relative}")
    return resolved


def resolve_routes_dir(config: Mapping[str, object], project_root: Path) -> Path:
    """Resolve the canonical field or its historical config alias.

    Existing strict Stage-6/7 schemas still use ``approved_routes_run``. The
    value now identifies an input directory rather than a historical run.
    """
    current, legacy = config.get("approved_routes"), config.get("approved_routes_run")
    _require(current is not None or legacy is not None, "approved_routes is missing")
    if current is not None and legacy is not None:
        _require(Path(str(current)) == Path(str(legacy)), "conflicting approved_routes aliases")
    value = current if current is not None else legacy
    _require(isinstance(value, str) and bool(value), "approved_routes must be a non-empty string")
    # Legacy callers may intentionally supply an external restored input set.
    path = Path(value)
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def _map_name(value: object) -> str:
    _require(isinstance(value, str) and bool(value), "map_name must be a non-empty string")
    return value.rstrip("/").rsplit("/", 1)[-1].casefold()


def _verify_file(path: Path, expected: Mapping[str, object]) -> None:
    digest = expected.get("sha256")
    _require(isinstance(digest, str) and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), f"{path}: invalid SHA-256 declaration")
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise InputValidationError(f"missing input file {path}: {exc}") from exc
    if "bytes" in expected:
        _require(type(expected["bytes"]) is int and expected["bytes"] == len(payload), f"{path}: byte count mismatch")
    _require(hashlib.sha256(payload).hexdigest() == digest, f"{path}: SHA-256 mismatch")


def validate_route_set(routes_dir: Path, expected_map: str) -> dict[str, Any]:
    """Check pinned files and saved geometry; live navigation remains a VM check."""
    routes_dir = routes_dir.resolve()
    provenance = _object(routes_dir / "provenance.json")
    _require(_map_name(provenance.get("map_name")) == _map_name(expected_map), "route provenance map mismatch")
    files = provenance.get("files")
    _require(isinstance(files, dict) and bool(files), "route provenance files must be a non-empty object")
    for relative, signature in files.items():
        _require(isinstance(signature, dict), f"invalid signature for {relative}")
        _verify_file(_within(routes_dir, relative), signature)
    index = _object(routes_dir / "revised_routes.json")
    _require(_map_name(index.get("map_name")) == _map_name(expected_map), "route index map mismatch")
    step = _number(index.get("dense_step_m"), "dense_step_m", positive=True)
    routes = index.get("routes")
    _require(isinstance(routes, list) and bool(routes), "route index routes must be a non-empty array")
    required_files = {"revised_routes.json"}
    identifiers: list[str] = []
    for item in routes:
        _require(isinstance(item, dict), "route index item must be an object")
        route_id = item.get("route_id")
        _require(isinstance(route_id, str) and bool(route_id) and route_id not in identifiers, "route IDs must be non-empty and unique")
        identifiers.append(route_id)
        relative = item.get("path")
        route_path = _within(routes_dir, relative)
        required_files.add(str(relative))
        document = _object(route_path)
        _require(document.get("candidate_id") == route_id, f"{route_id}: route ID mismatch")
        _require(_map_name(document.get("map_name")) == _map_name(expected_map), f"{route_id}: map mismatch")
        dense, adaptive = document.get("dense_reference"), document.get("adaptive_proposal")
        _require(isinstance(dense, dict) and isinstance(adaptive, dict), f"{route_id}: waypoint sets are missing")
        _require(abs(_number(dense.get("step_m"), "route step", positive=True) - step) < 1e-6, f"{route_id}: dense step mismatch")
        points = dense.get("waypoints")
        _require(isinstance(points, list) and len(points) >= 10, f"{route_id}: insufficient dense waypoints")
        _require(dense.get("waypoint_count") == len(points) == item.get("dense_waypoint_count"), f"{route_id}: dense count mismatch")
        indices = adaptive.get("dense_indices")
        _require(isinstance(indices, list) and len(indices) >= 10 and all(type(i) is int for i in indices), f"{route_id}: invalid adaptive indices")
        _require(indices == sorted(set(indices)) and indices[0] == 0 and indices[-1] == len(points) - 1, f"{route_id}: adaptive indices do not cover ordered dense endpoints")
        _require(adaptive.get("waypoint_count") == len(indices) == item.get("adaptive_waypoint_count"), f"{route_id}: adaptive count mismatch")
        locations = []
        for point in points:
            _require(isinstance(point, dict) and isinstance(point.get("transform"), dict), f"{route_id}: malformed waypoint")
            transform = point["transform"]
            location, rotation = transform.get("location"), transform.get("rotation")
            _require(isinstance(location, dict) and isinstance(rotation, dict), f"{route_id}: malformed transform")
            locations.append(tuple(_number(location.get(axis), f"{route_id}.{axis}") for axis in ("x", "y", "z")))
            for axis in ("pitch", "yaw", "roll"):
                _number(rotation.get(axis), f"{route_id}.{axis}")
            for key in ("road_id", "lane_id", "waypoint_id"):
                _require(type(point.get(key)) is int, f"{route_id}: invalid navigation identity {key}")
            _number(point.get("s"), f"{route_id}.s")
        length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(locations, locations[1:]))
        _require(abs(length - _number(document.get("length_m"), "length_m", positive=True)) <= 0.25, f"{route_id}: reconstructed length mismatch")
        _require(abs(length - _number(item.get("length_m"), "index length_m", positive=True)) <= 0.25, f"{route_id}: index length mismatch")
    _require(set(files) == required_files, "route provenance must pin exactly the index and indexed route files")
    selection = provenance.get("selection")
    _require(isinstance(selection, dict) and selection.get("route_ids") == identifiers, "route provenance selection mismatch")
    return {"route_ids": identifiers, "map_name": index["map_name"], "files_verified": len(files)}


def validate_calibration(calibration_path: Path) -> dict[str, int]:
    document = _object(calibration_path)
    source = document.get("source")
    _require(isinstance(source, dict) and isinstance(source.get("files"), dict) and bool(source["files"]), "calibration source files are missing")
    for relative, digest in source["files"].items():
        _verify_file(_within(calibration_path.parent, relative), {"sha256": digest})
    cameras = document.get("cameras")
    _require(isinstance(cameras, list) and all(isinstance(c, dict) for c in cameras), "calibration cameras must be an array of objects")
    names = [camera.get("sensor_name") for camera in cameras]
    _require(len(names) == len(CAMERA_ORDER) and set(names) == set(CAMERA_ORDER), "calibration must contain the canonical nine AV2 cameras once each")
    for camera in cameras:
        pose, intrinsics = camera.get("egovehicle_SE3_sensor"), camera.get("intrinsics")
        _require(isinstance(pose, dict) and isinstance(intrinsics, dict), "camera pose/intrinsics are missing")
        values = {key: _number(pose.get(key), key) for key in ("qw", "qx", "qy", "qz", "tx_m", "ty_m", "tz_m")}
        norm = sum(values[key] ** 2 for key in ("qw", "qx", "qy", "qz"))
        _require(abs(norm - 1) < 1e-5, "camera quaternion is not unit length")
        for key in ("fx_px", "fy_px", "width_px", "height_px"):
            _number(intrinsics.get(key), key, positive=True)
        for key in ("cx_px", "cy_px"):
            _number(intrinsics.get(key), key)
    return {"camera_positions": len(cameras), "source_files_verified": len(source["files"])}


def validate_inputs(project_root: Path = Path("."), config_paths: Sequence[Path | str] | None = None) -> dict[str, Any]:
    """Return a concise validation report for selected maintained configurations.

    This confirms portable file integrity and structural compatibility, not
    live map connectivity, asset availability, or camera occlusion.
    """
    root = project_root.resolve()
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    config_cache: dict[Path, dict[str, Any]] = {}
    route_cache: dict[tuple[Path, str], dict[str, Any]] = {}
    calibration_cache: dict[Path, dict[str, int]] = {}

    def load_config(relative: Path | str) -> dict[str, Any]:
        path = _within(root, relative)
        if path not in config_cache:
            config_cache[path] = _object(path)
        return config_cache[path]

    for relative in DEFAULT_CONFIGS if config_paths is None else config_paths:
        try:
            config = load_config(relative)
            map_name = config.get("map_name")
            _map_name(map_name)
            # Offline validation is deliberately limited to checkout-owned inputs.
            routes_dir = resolve_routes_dir(config, root)
            _require(routes_dir.is_relative_to(root), "route inputs escape project root")
            route_key = (routes_dir, str(map_name))
            if route_key not in route_cache:
                route_cache[route_key] = validate_route_set(routes_dir, str(map_name))
            route_ids = config.get("route_ids", config.get("allowed_route_ids", [config.get("route_id")]))
            _require(isinstance(route_ids, list) and bool(route_ids) and all(isinstance(i, str) and i in route_cache[route_key]["route_ids"] for i in route_ids), "config selects unknown route IDs")
            weather = config
            if "weather_source_config" in config:
                weather = load_config(config["weather_source_config"])
                _require(_map_name(weather.get("map_name")) == _map_name(map_name), "weather source map mismatch")
            profiles = weather.get("weather_profiles")
            _require(isinstance(profiles, dict) and bool(profiles), "weather profiles are missing")
            for weather_id, profile in profiles.items():
                _require(isinstance(profile, dict) and isinstance(profile.get("parameters"), dict) and bool(profile["parameters"]), f"{weather_id}: weather parameters are missing")
                for parameter, value in profile["parameters"].items():
                    _number(value, f"{weather_id}.{parameter}")
            selected = config.get("allowed_weather_ids", [config["weather_id"]] if "weather_id" in config else list(profiles))
            _require(isinstance(selected, list) and bool(selected) and all(isinstance(i, str) and i in profiles for i in selected), "config selects unknown weather IDs")
            if "scene_spec_config" in config:
                scene = load_config(config["scene_spec_config"])
                _require(_map_name(scene.get("map_name")) == _map_name(map_name), "scene protocol map mismatch")
                _require(config.get("route_id") in scene.get("allowed_route_ids", []), "probe route is not allowed by scene protocol")
                _require(config.get("weather_id") in scene.get("allowed_weather_ids", []), "probe weather is not allowed by scene protocol")
            camera = config.get("camera", {})
            _require(isinstance(camera, dict), "config camera must be an object")
            timing = config.get("short_validation", config.get("motion", config))
            _require(isinstance(timing, dict), "config timing must be an object")
            if "fixed_delta_seconds" in timing:
                fixed = _number(timing["fixed_delta_seconds"], "fixed_delta_seconds", positive=True)
                sensor_tick = camera.get("sensor_tick_seconds", timing.get("sensor_tick_seconds"))
                if sensor_tick is not None:
                    ratio = _number(sensor_tick, "sensor_tick_seconds", positive=True) / fixed
                    _require(abs(ratio - round(ratio)) < 1e-9, "sensor tick must be an integer multiple of fixed delta")
            calibration_path = _within(root, camera.get("calibration", DEFAULT_CALIBRATION))
            if calibration_path not in calibration_cache:
                calibration_cache[calibration_path] = validate_calibration(calibration_path)
            if "name" in camera:
                _require(camera["name"] in CAMERA_ORDER, "unknown camera name")
            checks.append({"config": str(relative), "valid": True, "route_count": len(route_ids)})
        except (InputValidationError, TypeError, ValueError) as exc:
            errors.append(f"{relative}: {exc}")
            checks.append({"config": str(relative), "valid": False})
    return {
        "valid": not errors and bool(checks), "checks": checks, "errors": errors,
        "route_sets_verified": len(route_cache), "calibrations_verified": len(calibration_cache),
        "scope": "Portable inputs only; historical runs, GPU, CARLA and APIs are not accessed.",
    }
