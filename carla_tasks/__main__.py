"""Shared command entry point. Offline commands do not import CARLA."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def emit(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def main() -> int:
    if sys.argv[1:2] == ["validate-dataset"]:
        from .dataset import main as validate
        sys.argv = ["validate-dataset", *sys.argv[2:]]
        try:
            validate()
        except (OSError, ValueError) as exc:
            emit({"status": "error", "reason": str(exc)})
            return 2
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check-docs", help="check startup budget, links and preserved archive hashes")
    check = commands.add_parser("check-inputs", help="verify small Git-tracked runtime inputs")
    check.add_argument("--config", type=Path, action="append")
    scene = commands.add_parser("scene-check", help="offline validation of the static SceneSpec v1.0 envelope")
    scene.add_argument("scene", type=Path)
    scene.add_argument("--config", type=Path, default=Path("configs/stage6_scene_editing.json"))
    plan = commands.add_parser("plan", help="resolve matrix identity and repeats without CARLA")
    plan.add_argument("--config", type=Path, default=Path("configs/stage4_baseline_matrix.json"))
    plan.add_argument("--calibration", type=Path)
    verify = commands.add_parser("verify-export", help="rehash a copied run against its manifest")
    verify.add_argument("source_run", type=Path)
    verify.add_argument("external_copy", type=Path)
    dataset = commands.add_parser("validate-dataset", help="validate a stored RGB/semantic recording")
    dataset.add_argument("arguments", nargs=argparse.REMAINDER)
    server = commands.add_parser("server-status", help="read-only RPC readiness check on the VM")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=2000)
    server.add_argument("--timeout", type=float, default=2.0)
    server.add_argument("--quiet", action="store_true")
    processes = commands.add_parser("process", help="durable child process start/status/wait")
    actions = processes.add_subparsers(dest="action", required=True)
    start = actions.add_parser("start")
    start.add_argument("--state", type=Path, required=True)
    start.add_argument("--log", type=Path, required=True)
    start.add_argument("--cwd", type=Path, default=Path.cwd())
    start.add_argument("arguments", nargs=argparse.REMAINDER)
    for action in ("status", "wait"):
        sub = actions.add_parser(action)
        sub.add_argument("--state", type=Path, required=True)
        if action == "wait":
            sub.add_argument("--timeout", type=float, default=60.0)
    registry = commands.add_parser("registry", help="small portable run registry")
    registry.add_argument("--path", type=Path, default=Path("artifacts/run_registry.jsonl"))
    records = registry.add_subparsers(dest="action", required=True)
    listing = records.add_parser("list")
    listing.add_argument("--experiment-id")
    listing.add_argument("--limit", type=int, default=20)
    register = records.add_parser("import")
    register.add_argument("--run-dir", type=Path, required=True)
    copied = records.add_parser("verify-copy")
    copied.add_argument("--run-id", required=True)
    copied.add_argument("--manifest-dir", type=Path, required=True)
    copied.add_argument("--copy", type=Path, required=True)
    copied.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "check-docs":
            from .maintenance import check_docs
            result = check_docs(Path.cwd())
            emit(result)
            return 0 if result["valid"] else 1
        if args.command == "check-inputs":
            from .inputs import validate_inputs
            result = validate_inputs(Path.cwd(), config_paths=args.config)
            emit(result)
            return 0 if result["valid"] else 1
        if args.command == "scene-check":
            from .scene_spec import load_stage6_config, load_route_geometry, parse_scene_spec_json, resolve_scene_spec
            config = load_stage6_config(args.config)
            specification = parse_scene_spec_json(args.scene.read_text())
            route = load_route_geometry(Path.cwd(), config, specification.route_id)
            resolved = resolve_scene_spec(specification, config, route)
            emit({"valid": True, "version": specification.version, "route_id": specification.route_id,
                  "edit_count": len(resolved.edits), "scope": "Local policy and geometry only; no CARLA execution"})
        elif args.command == "plan":
            from .experiments import resolve_experiment
            resolved = resolve_experiment(args.config, root=Path.cwd(), calibration_path=args.calibration)
            emit({"experiment_id": resolved.experiment_id, "config_fingerprint": resolved.config_fingerprint,
                  "cells": [{"route_id": cell.route_id, "weather_id": cell.weather_id,
                             "repeat_index": cell.repeat_index} for cell in resolved.cells]})
        elif args.command == "verify-export":
            from .exports import verify_export
            result = verify_export(args.source_run, args.external_copy)
            emit({**result, "failure_count": len(result["failures"]), "failures": result["failures"][:10]})
            return 0 if result["status"] == "passed" else 1
        elif args.command == "validate-dataset":
            from .dataset import main as validate
            sys.argv = ["validate-dataset", *args.arguments]
            validate()
        elif args.command == "server-status":
            from .server import server_status
            if not 1 <= args.port <= 65535 or args.timeout <= 0:
                raise ValueError("invalid server port or timeout")
            result = server_status(args.host, args.port, args.timeout)
            if not args.quiet:
                emit(result)
            return 0 if result["ready"] else 1
        elif args.command == "process":
            from .processes import read_status, start_process, wait_process
            if args.action == "start":
                command = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
                result = start_process(command, args.state, args.log, args.cwd)
            elif args.action == "status":
                result = read_status(args.state)
            else:
                result = wait_process(args.state, args.timeout)
            emit(result)
            if result.get("state") == "failed":
                return 1
        elif args.command == "registry":
            from .registry import RunRegistry
            registry = RunRegistry(args.path)
            if args.action == "import":
                emit(registry.import_run(args.run_dir))
            elif args.action == "verify-copy":
                from .exports import verify_export
                from .hosts import host_identity
                from .registry import utc_now
                previous = next((row for row in registry.latest() if row["run_id"] == args.run_id), None)
                if previous is None:
                    raise ValueError("run must already be registered before verifying an external copy")
                verification_host = host_identity()
                source_host = previous.get("execution_host_id")
                if not source_host or source_host == verification_host:
                    raise ValueError("external backup needs a different recorded execution host; use verify-export for a local self-check")
                if args.report.resolve().is_relative_to(args.copy.resolve()):
                    raise ValueError("verification report must be outside the immutable copied run")
                result = verify_export(args.manifest_dir, args.copy)
                if result["manifest_sha256"] != previous.get("manifest_sha256"):
                    raise ValueError("source manifest differs from the registered finalized run")
                evidence = {**result, "run_id": args.run_id, "verified_at_utc": utc_now(),
                            "source_host_id": source_host, "verification_host_id": verification_host}
                args.report.parent.mkdir(parents=True, exist_ok=True)
                with args.report.open("x") as report:
                    json.dump(evidence, report, indent=2, sort_keys=True)
                    report.write("\n")
                if result["status"] == "passed":
                    registry.append({**previous, "recorded_at_utc": utc_now(), "external_copy": {
                        "status": "verified", "location": result["external_location"],
                        "manifest_sha256": result["manifest_sha256"], "evidence_path": str(args.report),
                        "verified_at_utc": evidence["verified_at_utc"], "verification_method": "destination SHA-256",
                        "source_host_id": source_host, "verification_host_id": verification_host}})
                emit({"status": result["status"], "run_id": args.run_id,
                      "entries": result["entries"], "failure_count": len(result["failures"]),
                      "report": str(args.report)})
                return 0 if result["status"] == "passed" else 1
            else:
                if args.limit < 1:
                    raise ValueError("limit must be positive")
                values = registry.latest()
                if args.experiment_id:
                    values = [row for row in values if row["experiment_id"] == args.experiment_id]
                emit({"total_runs": len(values), "runs": values[-args.limit:]})
        return 0
    except (OSError, ValueError, KeyError) as exc:
        # Command arguments and environment are never echoed on failures.
        emit({"status": "error", "reason": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
