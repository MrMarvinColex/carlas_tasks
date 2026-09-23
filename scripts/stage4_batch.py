#!/usr/bin/env python3
"""Run the unfinished Stage-4 matrix cells sequentially and preserve every outcome.

The script is intentionally a supervisor, not another recorder: every cell still
uses stage4_baseline.py and is finalized into its own immutable run directory.
It never starts more than one CARLA recorder and stops at the first failed or
interrupted cell.  Run it inside tmux; use --dry-run before a long batch.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "runs"
LOGS_DIR = ROOT / "logs"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def successful_cells(config: dict[str, Any]) -> set[tuple[str, str]]:
    """Find only completed, validated, non-benchmark baseline cells."""
    expected_routes = set(config["route_ids"])
    expected_weather = set(config["weather_profiles"])
    complete: set[tuple[str, str]] = set()
    for candidate in RUNS_DIR.iterdir():
        if not candidate.is_dir():
            continue
        metadata_path = candidate / "metadata.json"
        baseline_path = candidate / "baseline_config.json"
        validation_path = candidate / "baseline_validation.json"
        if not (metadata_path.is_file() and baseline_path.is_file() and validation_path.is_file()):
            continue
        try:
            metadata = load_object(metadata_path)
            baseline = load_object(baseline_path)
            validation = load_object(validation_path)
        except (OSError, json.JSONDecodeError):
            continue
        route_id = baseline.get("route_id")
        weather_id = baseline.get("weather_id")
        if (
            metadata.get("stage") == 4
            and metadata.get("state") == "complete"
            and metadata.get("validation_status") == "passed"
            and validation.get("status") == "passed"
            and isinstance(route_id, str)
            and isinstance(weather_id, str)
            and route_id in expected_routes
            and weather_id in expected_weather
            and baseline.get("benchmark_simulation_s") in (None, 0, 0.0)
        ):
            complete.add((route_id, weather_id))
    return complete


def planned_cells(config: dict[str, Any]) -> list[tuple[str, str]]:
    cells = [(route_id, weather_id) for weather_id in config["weather_profiles"] for route_id in config["route_ids"]]
    random.Random(int(config["execution_order_seed"])).shuffle(cells)
    return cells


class CommandRunner:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.log_file = log_path.open("a", encoding="utf-8")
        self.active: subprocess.Popen[str] | None = None

    def write(self, text: str) -> None:
        print(text, flush=True)
        self.log_file.write(text + "\n")
        self.log_file.flush()

    def run(self, command: list[str]) -> int:
        self.write("$ " + " ".join(command))
        self.active = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert self.active.stdout is not None
        for line in self.active.stdout:
            self.write(line.rstrip("\n"))
        return_code = self.active.wait()
        self.active = None
        self.write(f"exit={return_code}")
        return return_code

    def interrupt_active(self) -> None:
        if self.active is not None and self.active.poll() is None:
            self.active.send_signal(signal.SIGINT)
            try:
                self.active.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.active.kill()
                self.active.wait()
        self.active = None

    def close(self) -> None:
        self.log_file.close()


def finalize_and_verify(runner: CommandRunner, run_dir: Path, state: str, reason: str) -> bool:
    finalize = [sys.executable, "scripts/finalize_run.py", str(run_dir), "--state", state, "--reason", reason]
    if runner.run(finalize) != 0:
        return False
    verify = [sys.executable, "scripts/verify_export.py", str(run_dir), str(run_dir)]
    return runner.run(verify) == 0


def create_run(runner: CommandRunner, route_id: str, weather_id: str) -> Path:
    before = {path.name for path in RUNS_DIR.iterdir() if path.is_dir()}
    label = f"baseline-{route_id}-{weather_id}"
    if runner.run([sys.executable, "scripts/create_run.py", "--stage", "4", "--label", label]) != 0:
        raise RuntimeError(f"could not create run for {route_id}/{weather_id}")
    created = [path for path in RUNS_DIR.iterdir() if path.is_dir() and path.name not in before]
    if len(created) != 1:
        raise RuntimeError(f"expected one new run directory for {route_id}/{weather_id}, found {len(created)}")
    return created[0]


def write_summary(path: Path, result: dict[str, Any]) -> None:
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-config", type=Path, default=Path("configs/stage4_baseline_matrix.json"))
    parser.add_argument("--writer-workers", type=int, default=4)
    parser.add_argument("--max-pending-write-samples", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true", help="list unfinished cells; do not start CARLA or write files")
    args = parser.parse_args()
    if args.writer_workers <= 0 or args.max_pending_write_samples <= 0:
        raise SystemExit("writer worker and pending-write counts must be positive")

    config_path = (ROOT / args.baseline_config).resolve() if not args.baseline_config.is_absolute() else args.baseline_config
    config = load_object(config_path)
    complete = successful_cells(config)
    remaining = [cell for cell in planned_cells(config) if cell not in complete]
    if args.dry_run:
        print(json.dumps({"completed_cells": sorted(complete), "remaining_cells": remaining}, indent=2))
        return 0
    if not remaining:
        print("all Stage-4 baseline cells are already complete and validated")
        return 0

    LOGS_DIR.mkdir(exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = LOGS_DIR / f"stage4-batch-{stamp}.log"
    summary_path = LOGS_DIR / f"stage4-batch-{stamp}.json"
    result: dict[str, Any] = {
        "started_at_utc": utc_now(),
        "baseline_config": str(config_path.relative_to(ROOT)),
        "completed_before_batch": [{"route_id": route, "weather_id": weather} for route, weather in sorted(complete)],
        "planned_cells": [{"route_id": route, "weather_id": weather} for route, weather in remaining],
        "results": [],
        "policy_note": "User authorized deferring external export for this batch; per-run minimum-free-disk checks remain active.",
        "status": "running",
    }
    runner = CommandRunner(log_path)
    server_started = False
    current_run: Path | None = None
    try:
        runner.write(f"Stage-4 batch begins at {result['started_at_utc']}; {len(remaining)} cells remain")
        if runner.run(["bash", "scripts/run_carla.sh"]) != 0:
            raise RuntimeError("CARLA did not start; no baseline cell was run")
        server_started = True
        for route_id, weather_id in remaining:
            current_run = create_run(runner, route_id, weather_id)
            cell: dict[str, Any] = {"route_id": route_id, "weather_id": weather_id, "run_dir": str(current_run.relative_to(ROOT)), "started_at_utc": utc_now()}
            code = runner.run(
                [
                    sys.executable,
                    "scripts/stage4_baseline.py",
                    "--run-dir",
                    str(current_run),
                    "--baseline-config",
                    str(config_path),
                    "--route-id",
                    route_id,
                    "--weather-id",
                    weather_id,
                    "--writer-workers",
                    str(args.writer_workers),
                    "--max-pending-write-samples",
                    str(args.max_pending_write_samples),
                ]
            )
            if code != 0:
                cell.update({"status": "failed", "recorder_exit_code": code, "finished_at_utc": utc_now()})
                result["results"].append(cell)
                finalize_and_verify(runner, current_run, "failed", f"batch recorder exited {code}")
                raise RuntimeError(f"recorder failed for {route_id}/{weather_id}; batch stopped")
            if not finalize_and_verify(runner, current_run, "complete", "batch baseline drive completed; validators passed"):
                cell.update({"status": "failed", "reason": "finalization or local manifest verification failed", "finished_at_utc": utc_now()})
                result["results"].append(cell)
                raise RuntimeError(f"finalization failed for {route_id}/{weather_id}; batch stopped")
            cell.update({"status": "passed", "finished_at_utc": utc_now()})
            result["results"].append(cell)
            current_run = None
        result["status"] = "passed"
        return 0
    except KeyboardInterrupt:
        runner.write("interrupted by user")
        runner.interrupt_active()
        if current_run is not None:
            finalize_and_verify(runner, current_run, "incomplete", "batch interrupted by user")
        result["status"] = "interrupted"
        return 130
    except Exception as exc:
        runner.write(f"batch failure: {exc}")
        result["status"] = "failed"
        result["error"] = str(exc)
        return 1
    finally:
        result["finished_at_utc"] = utc_now()
        write_summary(summary_path, result)
        runner.write(f"batch summary: {summary_path}")
        if server_started:
            stop_code = runner.run(["bash", "scripts/stop_carla.sh"])
            result["carla_stop_exit_code"] = stop_code
            write_summary(summary_path, result)
        runner.close()


if __name__ == "__main__":
    raise SystemExit(main())
