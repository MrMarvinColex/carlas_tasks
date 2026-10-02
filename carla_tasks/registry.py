"""Small append-only run ledger; output trees are never searched to resume work."""
from __future__ import annotations

import datetime as dt
import fcntl
import json
import re
from pathlib import Path
from typing import Any, Callable

from .experiments import Cell, ExperimentPlan, canonical_hash, file_sha256, load_object, measurement_fingerprint, validate_identifier


_HASH = re.compile(r"^[a-f0-9]{64}$")
TERMINAL_STATES = {"complete", "failed", "incomplete", "cancelled"}
_FIELDS = {
    "schema_version", "recorded_at_utc", "experiment_id", "config_fingerprint", "run_id", "route_id",
    "weather_id", "repeat_index", "state", "validation_status", "manifest_sha256", "local_run_dir",
    "external_copy", "evidence", "origin", "recorder_exit_code", "finalization_verified", "runtime_versions",
    "execution_host_id", "measurement_fingerprint", "last_copy_check",
}
_IDENTITY_FIELDS = ("schema_version", "experiment_id", "config_fingerprint", "measurement_fingerprint",
                    "route_id", "weather_id", "repeat_index")


def _same_run(previous: dict[str, Any], current: dict[str, Any]) -> None:
    fields = (*_IDENTITY_FIELDS, "execution_host_id")
    if any(previous.get(key) != current.get(key) for key in fields):
        raise ValueError("run_id already belongs to a different identity or execution host")
    if previous.get("manifest_sha256") and previous["manifest_sha256"] != current.get("manifest_sha256"):
        raise ValueError("finalized run_id cannot change its manifest")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validated_record(record: dict[str, Any]) -> dict[str, Any]:
    # Store only explicitly supported fields: no complete config, environment,
    # command arguments, raw model responses, or arbitrary metadata.
    value = {key: item for key, item in record.items() if key in _FIELDS}
    value.setdefault("schema_version", 1)
    value.setdefault("recorded_at_utc", utc_now())
    if type(value["schema_version"]) is not int or value["schema_version"] not in (1, 2):
        raise ValueError("unsupported registry schema_version")
    for field in ("experiment_id", "run_id", "route_id", "weather_id"):
        validate_identifier(value.get(field), field)
    if not _HASH.fullmatch(str(value.get("config_fingerprint", ""))):
        raise ValueError("config_fingerprint must be a SHA-256 hash")
    if value["schema_version"] == 2 and not _HASH.fullmatch(str(value.get("measurement_fingerprint", ""))):
        raise ValueError("measurement_fingerprint must be a SHA-256 hash for schema 2")
    repeat = value.get("repeat_index")
    if isinstance(repeat, bool) or not isinstance(repeat, int) or repeat < 1:
        raise ValueError("repeat_index must be a positive integer")
    if value.get("state") not in TERMINAL_STATES | {"running", "starting", "unknown"}:
        raise ValueError("unsupported run state")
    if value.get("validation_status", "not_run") not in {"passed", "failed", "not_run", "unknown"}:
        raise ValueError("unsupported validation status")
    manifest = value.get("manifest_sha256")
    if manifest is not None and not _HASH.fullmatch(str(manifest)):
        raise ValueError("manifest_sha256 must be a SHA-256 hash")
    if value.get("state") == "complete" and (value.get("validation_status") != "passed" or not manifest or not value.get("finalization_verified")):
        raise ValueError("complete records require passed validation and a verified local manifest")
    external = value.get("external_copy", {"status": "not_copied"})
    if not isinstance(external, dict):
        raise ValueError("external_copy must be an object")
    external = {key: item for key, item in external.items() if key in {"status", "location", "verified_at_utc", "evidence_path", "manifest_sha256", "verification_method", "source_host_id", "verification_host_id"}}
    if any(not isinstance(item, str) for item in external.values()):
        raise ValueError("external-copy fields must be strings")
    if external.get("status") not in {"not_copied", "unknown", "user_reported", "verified", "failed"}:
        raise ValueError("unsupported external-copy status")
    if external.get("status") == "verified" and (not external.get("location") or not external.get("evidence_path") or external.get("manifest_sha256") != manifest):
        raise ValueError("verified external copies require location, evidence and matching manifest hash")
    if external.get("status") == "verified" and (not external.get("source_host_id") or not external.get("verification_host_id") or external["source_host_id"] == external["verification_host_id"]):
        raise ValueError("verified external copies require distinct execution and verification hosts")
    if external.get("status") == "verified" and external["source_host_id"] != value.get("execution_host_id"):
        raise ValueError("external-copy source host differs from run execution host")
    value["external_copy"] = external
    if "last_copy_check" in value:
        # Apply the same field allowlist and provenance rules to the latest check.
        check = value.pop("last_copy_check")
        checked = _validated_record({**value, "external_copy": check})["external_copy"]
        if checked.get("status") not in {"verified", "failed"}:
            raise ValueError("last_copy_check must record a verification outcome")
        value["last_copy_check"] = checked
    if not isinstance(value.get("evidence", []), list) or any(not isinstance(item, str) for item in value.get("evidence", [])):
        raise ValueError("evidence must be a list of file references")
    versions = value.get("runtime_versions")
    if isinstance(versions, dict):
        value["runtime_versions"] = {key: item for key, item in versions.items() if key in {"carla_client_version", "carla_server_version", "image"}}
    # JSON encoding rejects NaN and unusual Python objects before touching disk.
    json.dumps(value, allow_nan=False)
    return value


class RunRegistry:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _read(self, stream: Any) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        stream.seek(0)
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("expected an object")
                records.append(_validated_record(record))
            except (ValueError, TypeError) as exc:
                raise ValueError(f"invalid registry record at {self.path}:{line_number}: {exc}") from exc
        return records

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_SH)
            return self._read(stream)

    def latest(self) -> list[dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for record in self.records():
            latest[record["run_id"]] = record
        return list(latest.values())

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        value = _validated_record(record)
        return self._update(value["run_id"], lambda previous: value)

    def _update(self, run_id: str, build: Callable[[dict[str, Any] | None], dict[str, Any]]) -> dict[str, Any]:
        """Read, merge and append under one lock; never overwrite a newer event."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            previous = next((row for row in reversed(self._read(stream)) if row["run_id"] == run_id), None)
            value = _validated_record(build(previous))
            if value["run_id"] != run_id:
                raise ValueError("registry update changed run_id")
            if previous:
                _same_run(previous, value)
                if {k: v for k, v in previous.items() if k != "recorded_at_utc"} == {k: v for k, v in value.items() if k != "recorded_at_utc"}:
                    return previous
            stream.seek(0, 2)
            stream.write(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
            stream.flush()
            __import__("os").fsync(stream.fileno())
        return value

    def record_copy_check(self, run_id: str, check: dict[str, str]) -> dict[str, Any]:
        def update(previous: dict[str, Any] | None) -> dict[str, Any]:
            if previous is None:
                raise ValueError("run must already be registered")
            if check.get("manifest_sha256") != previous.get("manifest_sha256"):
                raise ValueError("copy check differs from registered manifest")
            if check.get("status") not in {"verified", "failed"}:
                raise ValueError("copy check must be verified or failed")
            old = previous.get("external_copy", {})
            same_copy = all(old.get(key) == check.get(key) for key in ("location", "verification_host_id"))
            # A failed check invalidates this copy, not an independent good copy.
            selected = check if check["status"] == "verified" or same_copy or old.get("status") != "verified" else old
            return {**previous, "recorded_at_utc": utc_now(), "external_copy": selected, "last_copy_check": check}
        return self._update(run_id, update)

    def cell_status(self, plan: ExperimentPlan, cell: Cell, *, records: list[dict[str, Any]] | None = None) -> str:
        matching = [record for record in (records if records is not None else self.latest()) if
                    record["experiment_id"] == plan.experiment_id and (
                        record.get("measurement_fingerprint") == measurement_fingerprint(plan.resolved_manifest, cell)
                        if record["schema_version"] == 2 else record["config_fingerprint"] == plan.config_fingerprint)
                    and all(record[key] == value for key, value in cell.as_dict().items())]
        if any(record["state"] not in TERMINAL_STATES for record in matching):
            return "blocked"
        complete = [record for record in matching if record["state"] == "complete" and record["validation_status"] == "passed" and record.get("finalization_verified")]
        for record in complete:
            external = record.get("external_copy", {})
            if external.get("status") == "verified" and external.get("manifest_sha256") == record.get("manifest_sha256"):
                return "complete"
            local = Path(record.get("local_run_dir", "")) / "manifest.sha256"
            last_check = record.get("last_copy_check", {})
            known_bad_local = (last_check.get("status") == "failed" and
                               Path(last_check.get("location", "")).resolve() == local.parent.resolve())
            if not known_bad_local and local.is_file() and file_sha256(local) == record.get("manifest_sha256"):
                return "complete"
        if complete:
            return "unavailable"
        return "pending"

    def import_run(self, run_dir: Path) -> dict[str, Any]:
        """Explicit import of a new-format run, verifying its complete manifest.

        Historical runs have no experiment identity and are deliberately refused;
        assigning them today's implementation hash would fabricate equivalence.
        Their original evidence remains in artifacts/index.csv and the archive.
        Import validates local files only and never infers an external backup.
        """
        run_dir = Path(run_dir).resolve()
        identity_path = run_dir / "experiment_identity.json"
        if not identity_path.is_file():
            raise ValueError("run has no recorded experiment identity; legacy runs require an explicitly audited migration, not today's fingerprint")
        identity = load_object(identity_path)
        resolved_manifest = load_object(run_dir / "experiment_manifest.json")
        if canonical_hash(resolved_manifest) != identity.get("config_fingerprint"):
            raise ValueError("recorded experiment manifest differs from its identity fingerprint")
        if identity.get("schema_version") == 2 and identity.get("measurement_fingerprint") != measurement_fingerprint(
                resolved_manifest, Cell(identity["route_id"], identity["weather_id"], identity["repeat_index"])):
            raise ValueError("recorded measurement fingerprint differs from selected inputs")
        metadata = load_object(run_dir / "metadata.json")
        if metadata.get("run_id") != run_dir.name or any(metadata.get(key) != identity.get(key) for key in
                ("experiment_id", "config_fingerprint", "measurement_fingerprint", "route_id", "weather_id", "repeat_index")):
            raise ValueError("metadata disagrees with recorded run/experiment identity")
        baseline = load_object(run_dir / "baseline_config.json")
        if baseline.get("benchmark_simulation_s") not in (None, 0, 0.0):
            raise ValueError("throughput benchmarks are not matrix drives")
        if baseline.get("route_id") != identity.get("route_id") or baseline.get("weather_id") != identity.get("weather_id"):
            raise ValueError("run outputs disagree with recorded experiment cell")
        manifest_path = run_dir / "manifest.sha256"
        if not manifest_path.is_file():
            raise ValueError("run must be finalized before importing")
        signed_paths: set[str] = set()
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            try:
                digest, size, relative = line.split("  ", 2)
                path = (run_dir / relative).resolve()
                if not _HASH.fullmatch(digest) or not path.is_relative_to(run_dir) or relative in signed_paths:
                    raise ValueError("invalid path or digest")
                if path.stat().st_size != int(size) or file_sha256(path) != digest:
                    raise ValueError(f"hash/size mismatch: {relative}")
                signed_paths.add(relative)
            except (ValueError, OSError) as exc:
                raise ValueError(f"manifest verification failed: {exc}") from exc
        if not {"metadata.json", "experiment_identity.json", "experiment_manifest.json", "baseline_config.json"}.issubset(signed_paths):
            raise ValueError("manifest must sign metadata, baseline config, experiment identity and experiment manifest")
        state = metadata.get("state", "unknown")
        validation = "unknown"
        if state == "complete":
            validation_path = run_dir / "baseline_validation.json"
            if "baseline_validation.json" not in signed_paths or load_object(validation_path).get("status") != "passed":
                raise ValueError("complete imported drive lacks signed passed baseline validation")
            validation = "passed"
            expected_runtime = resolved_manifest.get("runtime", {})
            if any(metadata.get(field) != expected_runtime.get(field) for field in ("carla_client_version", "carla_server_version")):
                raise ValueError("CARLA runtime versions differ from the recorded experiment plan")
        elif state in TERMINAL_STATES:
            validation = "failed"
        else:
            raise ValueError("import requires terminal run metadata")
        imported = {
            **identity, "run_id": run_dir.name, "state": state, "validation_status": validation,
            "manifest_sha256": file_sha256(manifest_path), "finalization_verified": True,
            "local_run_dir": str(run_dir), "external_copy": {"status": "unknown"},
            "origin": "explicit_local_import", "evidence": ["experiment_identity.json", "metadata.json", "baseline_validation.json", "manifest.sha256"],
            "execution_host_id": metadata.get("execution_host_id"),
            "runtime_versions": {"carla_client_version": metadata.get("carla_client_version"),
                                 "carla_server_version": metadata.get("carla_server_version"),
                                 "image": resolved_manifest.get("runtime", {}).get("server_image")},
        }
        def update(previous: dict[str, Any] | None) -> dict[str, Any]:
            if previous:
                _same_run(previous, imported)
                # Rehashing a local copy neither creates nor erases external proof.
                return {**previous, "local_run_dir": str(run_dir), "recorded_at_utc": utc_now()}
            return imported
        return self._update(run_dir.name, update)


def run_record(plan: ExperimentPlan, cell: Cell, run_dir: Path, state: str, *, validation_status: str = "not_run", manifest_verified: bool = False, recorder_exit_code: int | None = None) -> dict[str, Any]:
    manifest_path = run_dir / "manifest.sha256"
    versions: dict[str, Any] = {}
    execution_host_id = None
    if (run_dir / "metadata.json").is_file():
        metadata = load_object(run_dir / "metadata.json")
        versions = {key: metadata[key] for key in ("carla_client_version", "carla_server_version") if key in metadata}
        execution_host_id = metadata.get("execution_host_id")
    versions["image"] = plan.resolved_manifest["runtime"]["server_image"]
    return {
        **plan.identity(cell), "run_id": run_dir.name, "state": state, "validation_status": validation_status,
        "manifest_sha256": file_sha256(manifest_path) if manifest_path.is_file() else None,
        "finalization_verified": manifest_verified, "local_run_dir": str(run_dir),
        "external_copy": {"status": "not_copied"}, "origin": "batch",
        "recorder_exit_code": recorder_exit_code, "runtime_versions": versions,
        "execution_host_id": execution_host_id,
        "evidence": ["experiment_identity.json", "metadata.json", "baseline_validation.json", "manifest.sha256"],
    }
