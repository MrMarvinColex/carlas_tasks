"""Small world lifecycle helpers; importable without the CARLA Python wheel."""
from __future__ import annotations

import math
import fcntl
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator


class RecorderBusyError(RuntimeError):
    pass


@contextmanager
def recorder_lock(path: Path) -> Iterator[None]:
    """One supported capture command per checkout; OS releases on process exit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RecorderBusyError("another capture owns the recorder lock; inspect its process before retrying") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def run_capture_entrypoint(action: Callable[[], Any]) -> int:
    # Help must remain read-only. The lock guards commands, not helper imports.
    if "--help" in sys.argv[1:] or "-h" in sys.argv[1:]:
        return action() or 0
    try:
        with recorder_lock(Path(__file__).resolve().parents[1] / "logs/carla-recorder.lock"):
            return action() or 0
    except RecorderBusyError as exc:
        print(str(exc), file=sys.stderr)
        return 2


def validate_capture_timing(fixed_delta_seconds: float, sensor_tick_seconds: float) -> None:
    if not all(math.isfinite(value) and value > 0 for value in (fixed_delta_seconds, sensor_tick_seconds)):
        raise ValueError("simulation and sensor steps must be finite and positive")
    ratio = sensor_tick_seconds / fixed_delta_seconds
    if not math.isclose(ratio, round(ratio), abs_tol=1e-9, rel_tol=0.0):
        raise ValueError("sensor period must be an integer multiple of the world step")


def configure_synchronous_world(world: Any, fixed_delta_seconds: float = 0.05) -> dict[str, object]:
    if not math.isfinite(fixed_delta_seconds) or fixed_delta_seconds <= 0:
        raise ValueError("world step must be finite and positive")
    settings = world.get_settings()
    if getattr(settings, "substepping", False):
        capacity = settings.max_substeps * settings.max_substep_delta_time
        if fixed_delta_seconds > capacity + 1e-12:
            raise ValueError("world step exceeds the configured physics substep capacity")
    original = {
        "synchronous_mode": bool(settings.synchronous_mode),
        "fixed_delta_seconds": settings.fixed_delta_seconds,
        "no_rendering_mode": bool(settings.no_rendering_mode),
    }
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = fixed_delta_seconds
    settings.no_rendering_mode = False
    world.apply_settings(settings)
    world.tick()
    return original


def restore_world_settings(world: Any, original: dict[str, object]) -> None:
    settings = world.get_settings()
    settings.synchronous_mode = bool(original["synchronous_mode"])
    settings.fixed_delta_seconds = original["fixed_delta_seconds"]
    settings.no_rendering_mode = bool(original["no_rendering_mode"])
    world.apply_settings(settings)
