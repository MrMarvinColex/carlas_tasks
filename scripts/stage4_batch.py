#!/usr/bin/env python3
"""Resume explicit measurement repeats from a small ledger, with one recorder."""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import secrets
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from carla_tasks.experiments import DEFAULT_REGISTRY, Cell, ExperimentPlan, load_object, resolve_experiment
from carla_tasks.registry import RunRegistry, run_record, utc_now

RUNS_DIR = ROOT / "runs"
LOGS_DIR = ROOT / "logs"


def planned_cells(config: dict[str, Any]) -> list[Cell]:
    import random
    repeats = config.get("repeats_per_route_weather", 1)
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
        raise ValueError("repeats_per_route_weather must be a positive integer")
    cells = [Cell(route, weather, repeat) for repeat in range(1, repeats + 1) for weather in config["weather_profiles"] for route in config["route_ids"]]
    random.Random(int(config["execution_order_seed"])).shuffle(cells)
    return cells


def plan_status(plan: ExperimentPlan, registry: RunRegistry) -> dict[str, Any]:
    records = registry.latest()
    groups: dict[str, list[dict[str, Any]]] = {"complete": [], "pending": [], "blocked": [], "unavailable": []}
    for cell in plan.cells:
        groups[registry.cell_status(plan, cell, records=records)].append(cell.as_dict())
    return {"experiment_id": plan.experiment_id, "config_fingerprint": plan.config_fingerprint,
            "completed_cells": groups["complete"], "remaining_cells": groups["pending"], "blocked_cells": groups["blocked"], "unavailable_cells": groups["unavailable"]}


class CommandRunner:
    def __init__(self, log_path: Path) -> None:
        self.log_file = log_path.open("a", encoding="utf-8")
        self.active: subprocess.Popen[str] | None = None

    def write(self, text: str) -> None:
        print(text, flush=True)
        self.log_file.write(text + "\n")
        self.log_file.flush()

    def run(self, command: list[str], *, env: dict[str, str] | None = None) -> int:
        self.write("$ " + " ".join(command))
        self.active = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, bufsize=1, start_new_session=True, env=env)
        assert self.active.stdout is not None
        try:
            for line in self.active.stdout:
                self.write(line.rstrip("\n"))
            code = self.active.wait()
        finally:
            if self.active is not None and self.active.poll() is not None:
                self.active.stdout.close()
                self.active = None
        self.write(f"exit={code}")
        return code

    def interrupt_active(self) -> None:
        if self.active is not None and self.active.poll() is None:
            os.killpg(self.active.pid, signal.SIGINT)
            try:
                self.active.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(self.active.pid, signal.SIGKILL)
                self.active.wait()
        if self.active is not None and self.active.stdout is not None:
            self.active.stdout.close()
        self.active = None

    def close(self) -> None:
        self.log_file.close()


def finalize_and_verify(runner: CommandRunner, run_dir: Path, state: str, reason: str) -> bool:
    if runner.run([sys.executable, "scripts/finalize_run.py", str(run_dir), "--state", state, "--reason", reason]) != 0:
        return False
    return runner.run([sys.executable, "scripts/verify_export.py", str(run_dir), str(run_dir)]) == 0


def write_summary(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def create_run(runner: CommandRunner, plan: ExperimentPlan, cell: Cell) -> Path:
    label = f"baseline-{cell.route_id}-{cell.weather_id}-r{cell.repeat_index}"[:80]
    run_id = f"{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}-{label}-{secrets.token_hex(3)}"
    run_dir = RUNS_DIR / run_id
    command = [sys.executable, "scripts/create_run.py", "--stage", "4", "--label", label,
               "--runs-dir", str(RUNS_DIR), "--run-id", run_id]
    if runner.run(command) != 0 or not run_dir.is_dir():
        raise RuntimeError(f"could not create run for {cell}")
    write_summary(run_dir / "experiment_identity.json", plan.identity(cell))
    write_summary(run_dir / "experiment_manifest.json", plan.resolved_manifest)
    write_summary(run_dir / "resolved_baseline_config.json", plan.config)
    metadata_path = run_dir / "metadata.json"
    metadata = load_object(metadata_path)
    metadata.update(plan.identity(cell))
    metadata["carla_image"] = plan.resolved_manifest["runtime"]["server_image"]
    write_summary(metadata_path, metadata)
    return run_dir


def recorder_command(plan: ExperimentPlan, cell: Cell, run_dir: Path) -> list[str]:
    runtime = plan.resolved_manifest["runtime"]
    return [sys.executable, "scripts/stage4_baseline.py", "--run-dir", str(run_dir),
            "--baseline-config", str(run_dir / "resolved_baseline_config.json"), "--calibration", str(plan.calibration_path),
            "--route-id", cell.route_id, "--weather-id", cell.weather_id,
            "--writer-workers", str(runtime["writer_workers"]), "--max-pending-write-samples", str(runtime["max_pending_write_samples"]),
            "--host", str(runtime["host"]), "--port", str(runtime["port"])]


def assert_identity_unchanged(plan: ExperimentPlan) -> None:
    """Catch input/code edits during server startup or an active recording.

    This reads only the declared small inputs and implementation files. It does
    not search outputs, import CARLA, or change the authoritative run snapshot.
    """
    current = resolve_experiment(plan.config_path, root=ROOT, calibration_path=plan.calibration_path,
                                 runtime_options=plan.resolved_manifest["runtime"],
                                 implementation_files=tuple(plan.resolved_manifest["implementation_sha256"]))
    if current.config_fingerprint != plan.config_fingerprint or current.experiment_id != plan.experiment_id:
        raise ValueError("experiment inputs/configuration/implementation changed after planning; recording is not accepted")


def _interrupt(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-config", type=Path, default=Path("configs/stage4_baseline_matrix.json"))
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--registry", type=Path, default=Path(DEFAULT_REGISTRY))
    parser.add_argument("--writer-workers", type=int, default=4)
    parser.add_argument("--max-pending-write-samples", type=int, default=8)
    parser.add_argument("--attach-server", action="store_true", help="explicitly attach to a healthy matching server; never stop a server owned by another launch")
    parser.add_argument("--dry-run", action="store_true", help="read portable inputs and ledger only; no writes, Docker or CARLA imports")
    args = parser.parse_args()
    if args.writer_workers <= 0 or args.max_pending_write_samples <= 0:
        parser.error("writer worker and pending-write counts must be positive")
    try:
        port = int(os.environ.get("CARLA_PORT", "2000"))
        if not 1 <= port <= 65535:
            raise ValueError("CARLA_PORT must be between 1 and 65535")
        plan = resolve_experiment(args.baseline_config, root=ROOT, calibration_path=args.calibration,
                                  runtime_options={"writer_workers": args.writer_workers, "max_pending_write_samples": args.max_pending_write_samples,
                                                   "host": os.environ.get("CARLA_HOST", "127.0.0.1"), "port": port})
        registry = RunRegistry(args.registry if args.registry.is_absolute() else ROOT / args.registry)
        status = plan_status(plan, registry)
    except (ValueError, OSError, KeyError) as exc:
        parser.error(str(exc))
    if args.dry_run:
        print(json.dumps(status, indent=2, sort_keys=True))
        return 0
    if status["blocked_cells"] or status["unavailable_cells"]:
        print("refusing launch: matching runs are nonterminal/unknown or completed data have no accessible manifest/verified external copy", file=sys.stderr)
        return 2
    if not status["remaining_cells"]:
        print("all requested experiment repeats are complete and validated")
        return 0
    LOGS_DIR.mkdir(exist_ok=True)
    lock = (LOGS_DIR / "stage4-batch.lock").open("a", encoding="utf-8")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        print("another Stage-4 batch owns the recorder lock", file=sys.stderr)
        return 2
    status = plan_status(plan, registry)
    if status["blocked_cells"] or status["unavailable_cells"]:
        lock.close()
        print("matching run became nonterminal before the lock was acquired", file=sys.stderr)
        return 2
    remaining = [Cell(**item) for item in status["remaining_cells"]]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)
    summary_path = LOGS_DIR / f"stage4-batch-{stamp}.json"
    lease_path = LOGS_DIR / f"stage4-batch-{stamp}-server-lease.json"
    launch_environment = {**os.environ, "CARLA_SERVER_LEASE": str(lease_path), "CARLA_IMAGE": plan.resolved_manifest["runtime"]["server_image"]}
    result: dict[str, Any] = {**status, "started_at_utc": utc_now(), "results": [], "status": "running",
                              "registry": str(registry.path), "external_copy_policy": "not_copied until separate verified export"}
    runner = CommandRunner(LOGS_DIR / f"stage4-batch-{stamp}.log")
    current_run: Path | None = None
    current_cell: Cell | None = None
    current_terminal = False
    previous_sigterm = signal.signal(signal.SIGTERM, _interrupt)
    try:
        write_summary(summary_path, result)
        start_command = ["bash", "scripts/run_carla.sh", *(["--attach"] if args.attach_server else [])]
        if runner.run(start_command, env=launch_environment) != 0:
            raise RuntimeError("CARLA startup failed; no recorder was started")
        for cell in remaining:
            assert_identity_unchanged(plan)
            current_cell, current_terminal = cell, False
            current_run = create_run(runner, plan, cell)
            registry.append(run_record(plan, cell, current_run, "running"))
            result["active_cell"] = {**cell.as_dict(), "run_id": current_run.name, "started_at_utc": utc_now()}
            write_summary(summary_path, result)
            code = runner.run(recorder_command(plan, cell, current_run))
            validation_path = current_run / "baseline_validation.json"
            passed = code == 0 and validation_path.is_file() and load_object(validation_path).get("status") == "passed"
            identity_error = None
            try:
                assert_identity_unchanged(plan)
            except (ValueError, OSError, KeyError) as exc:
                identity_error, passed = str(exc), False
                runner.write(identity_error)
            if passed:
                metadata = load_object(current_run / "metadata.json")
                runtime = plan.resolved_manifest["runtime"]
                passed = all(metadata.get(field) == runtime[field] for field in ("carla_client_version", "carla_server_version"))
            state = "complete" if passed else "failed"
            verified = finalize_and_verify(runner, current_run, state, "batch drive validators passed" if passed else identity_error or f"recorder exit={code}; validation/runtime checks did not pass")
            if not verified:
                state = "failed"
            registry.append(run_record(plan, cell, current_run, state, validation_status="passed" if passed and verified else "failed",
                                       manifest_verified=verified, recorder_exit_code=code))
            current_terminal = True
            result["results"].append({**cell.as_dict(), "run_id": current_run.name, "status": "passed" if state == "complete" else "failed", "finished_at_utc": utc_now()})
            if identity_error:
                result["results"][-1]["identity_error"] = identity_error
            result.pop("active_cell", None)
            write_summary(summary_path, result)
            current_run, current_cell = None, None
            if state != "complete":
                raise RuntimeError(f"failed recorder/validation/finalization for {cell}; batch stopped")
        result["status"] = "passed"
        return 0
    except KeyboardInterrupt:
        runner.write("batch interrupted; stopping the active process before recording terminal state")
        runner.interrupt_active()
        if current_run is not None and current_cell is not None and not current_terminal:
            verified = finalize_and_verify(runner, current_run, "incomplete", "batch interrupted")
            registry.append(run_record(plan, current_cell, current_run, "incomplete", validation_status="failed", manifest_verified=verified))
        result["status"] = "interrupted"
        return 130
    except Exception as exc:
        runner.interrupt_active()
        runner.write(f"batch failure: {exc}")
        if current_run is not None and current_cell is not None and not current_terminal:
            verified = finalize_and_verify(runner, current_run, "failed", "batch supervisor failed after stopping its recorder")
            registry.append(run_record(plan, current_cell, current_run, "failed", validation_status="failed", manifest_verified=verified))
        result.update(status="failed", error=str(exc))
        return 1
    finally:
        result["finished_at_utc"] = utc_now()
        result.pop("active_cell", None)
        write_summary(summary_path, result)
        if lease_path.is_file():
            result["carla_stop_exit_code"] = runner.run(["bash", "scripts/stop_carla.sh", "--lease", str(lease_path)])
            write_summary(summary_path, result)
        runner.write(f"batch summary: {summary_path}")
        runner.close()
        signal.signal(signal.SIGTERM, previous_sigterm)
        lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
