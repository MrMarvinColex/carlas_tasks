#!/usr/bin/env python3
"""Compatibility command for shared external-copy verification."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from carla_tasks.exports import main, sha256, verify_export  # noqa: E402

if __name__ == "__main__":
    main()
