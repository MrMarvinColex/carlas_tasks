#!/usr/bin/env python3
"""Create the minimal, auditable directory for one run without secrets."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import secrets
import subprocess
import sys
from pathlib import Path


def command_output(args: list[str]) -> str | None:
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=[str(n) for n in range(10)])
    parser.add_argument("--label", required=True)
    parser.add_argument("--runs-dir", default="runs")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    created = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    run_id = args.run_id or f"{created:%Y%m%dT%H%M%SZ}-{args.label}-{secrets.token_hex(3)}"
    if "/" in run_id or run_id in {".", ".."}:
        raise SystemExit("run ID must be a single path component")
    run_dir = Path(args.runs_dir) / run_id
    if run_dir.exists():
        raise SystemExit(f"refusing to overwrite existing run: {run_dir}")
    (run_dir / "logs").mkdir(parents=True)
    config = {
        "schema_version": 1,
        "run_id": run_id,
        "stage": int(args.stage),
        "label": args.label,
        "created_at_utc": created.isoformat().replace("+00:00", "Z"),
    }
    metadata = {
        **config,
        "state": "running",
        "git_commit": command_output(["git", "rev-parse", "HEAD"]),
        "git_dirty": bool(command_output(["git", "status", "--porcelain"])),
        "python": sys.version,
        "platform": platform.platform(),
        "carla_host": os.environ.get("CARLA_HOST", "127.0.0.1"),
        "carla_port": os.environ.get("CARLA_PORT", "2000"),
    }
    (run_dir / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    print(run_dir)


if __name__ == "__main__":
    main()
