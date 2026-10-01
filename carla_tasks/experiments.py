"""Portable experiment planning without CARLA, Docker, or old run directories."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .inputs import resolve_routes_dir


DEFAULT_CALIBRATION = "configs/av2/54bc6dbc-ebfb-3fba-b5b3-57f88b4b79ca/calibration.json"
DEFAULT_REGISTRY = "artifacts/run_registry.jsonl"
DEFAULT_CARLA_IMAGE = "carlasim/carla:0.9.16@sha256:aaf1df22702780ece072069e23d03c4879b002ae028c79744b09c4c7ddbae953"
IDENTITY_VERSION = 1
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_SECRET_KEYS = {"api_key", "apikey", "token", "access_token", "password", "secret", "authorization"}
_NON_RUNTIME_KEYS = {
    "description", "pilot", "disk_budget", "execution_order_seed", "repeats_per_route_weather",
    "experiment_id", "approved_routes", "approved_routes_run", "route_validation_run", "route_ids", "weather_profiles",
}


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{field} must be a short identifier using letters, digits, '.', '_' or '-'")
    return value


def _semantic_config(value: Any) -> Any:
    """Ignore explanatory text while refusing accidental credentials in snapshots."""
    if isinstance(value, dict):
        for key in value:
            if str(key).lower() in _SECRET_KEYS:
                raise ValueError(f"credentials must not appear in experiment configurations: {key}")
        return {key: _semantic_config(item) for key, item in value.items() if key != "description"}
    if isinstance(value, list):
        return [_semantic_config(item) for item in value]
    return value


def _path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return (root / path).resolve() if not path.is_absolute() else path.resolve()


def _label(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def source_dependency_hashes(root: Path, entrypoints: tuple[str, ...]) -> dict[str, str]:
    """Hash local Python imports recursively, never import GPU-only modules.

    Commit IDs and unrelated documentation do not affect equivalence. Explicit
    entrypoints also cover validators that the recorder invokes as subprocesses.
    """
    pending = [_path(root, entrypoint) for entrypoint in entrypoints]
    visited: set[Path] = set()
    hashes: dict[str, str] = {}
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        if not path.is_file():
            raise ValueError(f"missing experiment implementation dependency: {path}")
        hashes[_label(root, path)] = file_sha256(path)
        if path.suffix != ".py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = path.parent
                    for _ in range(node.level - 1):
                        base = base.parent
                    names = [node.module] if node.module else [alias.name for alias in node.names]
                    for name in names:
                        relative = Path(*name.split("."))
                        for candidate in (base / relative.with_suffix(".py"), base / relative / "__init__.py"):
                            if candidate.is_file():
                                pending.append(candidate.resolve())
                elif node.module:
                    modules = [node.module]
            for module in modules:
                relative = Path(*module.split("."))
                for base in (root, root / "scripts"):
                    for candidate in (base / relative.with_suffix(".py"), base / relative / "__init__.py"):
                        if candidate.is_file():
                            pending.append(candidate.resolve())
                    # Package initializers can affect imported modules too.
                    parts = relative.parts[:-1]
                    for depth in range(1, len(parts) + 1):
                        initializer = base.joinpath(*parts[:depth], "__init__.py")
                        if initializer.is_file():
                            pending.append(initializer.resolve())
    return dict(sorted(hashes.items()))


@dataclass(frozen=True)
class Cell:
    route_id: str
    weather_id: str
    repeat_index: int

    def as_dict(self) -> dict[str, Any]:
        return {"route_id": self.route_id, "weather_id": self.weather_id, "repeat_index": self.repeat_index}


@dataclass(frozen=True)
class ExperimentPlan:
    experiment_id: str
    config_fingerprint: str
    config_path: Path
    calibration_path: Path
    config: dict[str, Any]
    resolved_manifest: dict[str, Any]
    cells: tuple[Cell, ...]

    def identity(self, cell: Cell) -> dict[str, Any]:
        return {
            "schema_version": IDENTITY_VERSION,
            "experiment_id": self.experiment_id,
            "config_fingerprint": self.config_fingerprint,
            **cell.as_dict(),
        }


def resolve_experiment(
    config_path: Path,
    *,
    root: Path,
    calibration_path: Path | None = None,
    runtime_options: dict[str, Any] | None = None,
    implementation_files: tuple[str, ...] | None = None,
) -> ExperimentPlan:
    root = root.resolve()
    config_path = _path(root, config_path)
    config = load_object(config_path)
    experiment_id = validate_identifier(config.get("experiment_id"), "experiment_id")
    routes = config.get("route_ids")
    weather = config.get("weather_profiles")
    if not isinstance(routes, list) or not routes or len(routes) != len(set(routes)):
        raise ValueError("route_ids must be a nonempty list of unique route identifiers")
    for route_id in routes:
        validate_identifier(route_id, "route_id")
    if not isinstance(weather, dict) or not weather:
        raise ValueError("weather_profiles must be a nonempty object")
    for weather_id, profile in weather.items():
        validate_identifier(weather_id, "weather_id")
        if not isinstance(profile, dict) or not isinstance(profile.get("parameters"), dict) or not profile["parameters"]:
            raise ValueError(f"weather {weather_id} must have parameters")
    repeats = config.get("repeats_per_route_weather", 1)
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
        raise ValueError("repeats_per_route_weather must be a positive integer")
    for field in ("fixed_delta_seconds", "sensor_tick_seconds"):
        numeric = config.get(field)
        if isinstance(numeric, bool) or not isinstance(numeric, (int, float)) or numeric <= 0:
            raise ValueError(f"{field} must be positive")
    _semantic_config(config)
    routes_dir = resolve_routes_dir(config, root)
    index = load_object(routes_dir / "revised_routes.json")
    configured_map = str(config["map_name"]).split("/")[-1]
    if str(index.get("map_name", "")).split("/")[-1] != configured_map:
        raise ValueError("route index map differs from configured map")
    route_hashes: dict[str, str] = {}
    route_items = {item["route_id"]: item for item in index["routes"]}
    for route_id in sorted(routes):
        if route_id not in route_items:
            raise ValueError(f"route absent from approved route index: {route_id}")
        route_path = (routes_dir / str(route_items[route_id]["path"])).resolve()
        if not route_path.is_relative_to(routes_dir):
            raise ValueError("route input path must remain inside its input directory")
        route_doc = load_object(route_path)
        if str(route_doc.get("map_name", configured_map)).split("/")[-1] != configured_map:
            raise ValueError(f"route {route_id} map differs from configured map")
        # Historical source_run/location strings are provenance, not geometry.
        route_doc = {key: value for key, value in route_doc.items() if key not in {"source_run", "source_route", "source_file"}}
        route_hashes[route_id] = canonical_hash(_semantic_config(route_doc))
    calibration_path = _path(root, calibration_path or config.get("calibration", DEFAULT_CALIBRATION))
    calibration = load_object(calibration_path)
    raw_hashes: dict[str, str] = {}
    for relative, expected in calibration.get("source", {}).get("files", {}).items():
        raw_path = (calibration_path.parent / relative).resolve()
        if not raw_path.is_relative_to(calibration_path.parent):
            raise ValueError("raw calibration input must remain inside its input directory")
        actual = file_sha256(raw_path)
        if actual != expected:
            raise ValueError(f"calibration source hash mismatch: {relative}")
        raw_hashes[relative] = actual
    calibration_effective = {key: value for key, value in calibration.items() if key not in {"source", "description"}}
    implementation = implementation_files or (
        "scripts/stage4_baseline.py", "scripts/stage3_validate_dataset.py", "scripts/run_carla.sh", "requirements.txt",
    )
    runtime = {
        "server_image": os.environ.get("CARLA_IMAGE", DEFAULT_CARLA_IMAGE),
        "carla_client_version": "0.9.16",
        "carla_server_version": "0.9.16",
        "writer_workers": 4,
        "max_pending_write_samples": 8,
        "resource_sample_every": 10,
        "sensor_timeout_s": 30.0,
        "client_timeout_s": 60.0,
        "benchmark_simulation_s": 0.0,
        "host": os.environ.get("CARLA_HOST", "127.0.0.1"),
        "port": int(os.environ.get("CARLA_PORT", "2000")),
        **(runtime_options or {}),
    }
    image = runtime["server_image"]
    if not isinstance(image, str) or not re.fullmatch(r"(?:[^\s]+@)?sha256:[a-f0-9]{64}", image):
        raise ValueError("experiment CARLA_IMAGE must be an immutable @sha256 image reference or sha256 image ID")
    resolved: dict[str, Any] = {
        "schema_version": IDENTITY_VERSION,
        "settings": _semantic_config({key: value for key, value in config.items() if key not in _NON_RUNTIME_KEYS and key != "calibration"}),
        "weather_profiles": _semantic_config(weather),
        "routes": {"dense_step_m": index["dense_step_m"], "geometry_sha256": route_hashes},
        "calibration_sha256": canonical_hash(_semantic_config(calibration_effective)),
        "calibration_source_sha256": raw_hashes,
        "runtime": _semantic_config(runtime),
        "implementation_sha256": source_dependency_hashes(root, implementation),
    }
    cells = [Cell(route, weather_id, repeat) for repeat in range(1, repeats + 1) for weather_id in weather for route in routes]
    random.Random(int(config["execution_order_seed"])).shuffle(cells)
    return ExperimentPlan(experiment_id, canonical_hash(resolved), config_path, calibration_path, config, resolved, tuple(cells))
