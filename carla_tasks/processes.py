"""Durable process supervision without interpreting tool completion as run completion.

The supervisor owns the child and records its exit status. Readers never mark an
experiment failed merely because its result has not appeared or a PID vanished.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

TERMINAL = {"completed", "failed"}
_SUPERVISORS: dict[str, subprocess.Popen[str]] = {}


def _write(path: Path, state: dict[str, Any]) -> None:
    state["updated_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w") as handle:
        handle.write(json.dumps(state, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def read_status(path: Path) -> dict[str, Any]:
    state = json.loads(path.read_text())
    result = dict(state)
    if state.get("state") not in TERMINAL:
        pid = state.get("supervisor_pid")
        if isinstance(pid, int):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                result["observation"] = "unknown: supervisor absent; inspect result before retry"
            except PermissionError:
                result["observation"] = "unknown: supervisor inaccessible"
    return result


def start_process(command: list[str], state_path: Path, log_path: Path, cwd: Path) -> dict[str, Any]:
    if not command:
        raise ValueError("a command is required")
    state_path = state_path.resolve()
    log_path = log_path.resolve()
    cwd = cwd.resolve()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    state = {"schema_version": 1, "attempt_id": token, "state": "starting",
             "started_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
             "log_path": str(log_path), "cwd": str(cwd),
             "program": Path(command[0]).name, "exit_code": None}
    # Exclusive creation prevents a second launch when the outcome is unknown.
    descriptor = os.open(state_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(state, handle)
        handle.write("\n")
    environment = os.environ.copy()
    package_root = str(Path(__file__).resolve().parents[1])
    environment["PYTHONPATH"] = package_root + os.pathsep + environment.get("PYTHONPATH", "")
    try:
        supervisor = subprocess.Popen(
            [sys.executable, "-m", "carla_tasks.processes", str(state_path), str(log_path), str(cwd), token],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True, env=environment, text=True,
        )
        assert supervisor.stdin is not None
        # Command arguments are passed through a pipe, never persisted in status.
        supervisor.stdin.write(json.dumps(command))
        supervisor.stdin.close()
        _SUPERVISORS[token] = supervisor
    except (OSError, BrokenPipeError) as exc:
        state.update(state="failed", exit_code=-1, error=type(exc).__name__)
        _write(state_path, state)
        raise
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        current = read_status(state_path)
        if current.get("supervisor_pid") or current.get("state") in TERMINAL:
            return current
        if supervisor.poll() is not None:
            return {**current, "observation": "unknown: supervisor stopped before acknowledgement"}
        time.sleep(0.02)
    return {**read_status(state_path), "observation": "unknown: supervisor acknowledgement pending"}


def wait_process(path: Path, timeout_seconds: float = 60.0) -> dict[str, Any]:
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout must be positive")
    deadline = time.monotonic() + timeout_seconds
    while True:
        state = read_status(path)
        if state.get("state") in TERMINAL or state.get("observation") or time.monotonic() >= deadline:
            supervisor = _SUPERVISORS.get(state.get("attempt_id", ""))
            if supervisor is not None and state.get("state") in TERMINAL:
                try:
                    supervisor.wait(timeout=1)
                    _SUPERVISORS.pop(state["attempt_id"], None)
                except subprocess.TimeoutExpired:
                    pass
            outcome = ("finished" if state.get("state") in TERMINAL else
                       "unknown" if state.get("observation") or state.get("state") == "unknown" else "timeout")
            return {**state, "wait_outcome": outcome}
        time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))


def _supervise(state_path: Path, log_path: Path, cwd: Path, token: str, command: list[str]) -> int:
    state = read_status(state_path)
    if state.get("attempt_id") != token:
        return 2
    state.update(supervisor_pid=os.getpid(), state="starting")
    _write(state_path, state)
    started = time.monotonic()
    child: subprocess.Popen[Any] | None = None
    try:
        with log_path.open("x") as log:
            child = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL,
                                     stdout=log, stderr=subprocess.STDOUT)
            state.update(state="running", child_pid=child.pid)
            _write(state_path, state)
            while child.poll() is None:
                time.sleep(0.25)
                if time.monotonic() - float(state.get("heartbeat_monotonic", started)) >= 5:
                    state.update(elapsed_seconds=time.monotonic() - started,
                                 heartbeat_monotonic=time.monotonic())
                    _write(state_path, state)
            state.update(state="completed" if child.returncode == 0 else "failed",
                         exit_code=child.returncode, elapsed_seconds=time.monotonic() - started)
            state.pop("heartbeat_monotonic", None)
            _write(state_path, state)
    except Exception as exc:
        # Exception text may include command arguments; retain only its class.
        uncertain = child is not None and child.poll() is None
        state.update(state="unknown" if uncertain else "failed",
                     exit_code=None if uncertain else -1, error=type(exc).__name__)
        _write(state_path, state)
        return 1
    return 0


if __name__ == "__main__":
    supplied = json.load(sys.stdin)
    raise SystemExit(_supervise(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], supplied))
