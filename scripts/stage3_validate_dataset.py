#!/usr/bin/env python3
"""Compatibility command for the shared offline dataset validator."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from carla_tasks.dataset import *  # noqa: F401,F403,E402

if __name__ == "__main__":
    main()
