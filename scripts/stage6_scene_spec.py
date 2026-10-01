"""Compatibility exports for the shared passive SceneSpec validator."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from carla_tasks import scene_spec as _implementation
from carla_tasks.scene_spec import *  # noqa: F401,F403,E402


def __getattr__(name):
    return getattr(_implementation, name)
