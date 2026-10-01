import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
from carla_tasks.experiments import Cell, canonical_hash, file_sha256
from carla_tasks.registry import RunRegistry, run_record
from test_experiments import fixture, fixture_plan, write_json


class RegistryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.config = fixture(self.root)
        self.plan = fixture_plan(self.root)
        self.cell = self.plan.cells[0]
        self.registry = RunRegistry(self.root / "artifacts/run_registry.jsonl")
        self.run = self.root / "outputs/run-1"
        self.run.mkdir(parents=True)

    def record(self, state="complete"):
        (self.run / "manifest.sha256").write_text("fixture manifest")
        return {**run_record(self.plan, self.cell, self.run, state, validation_status="passed" if state == "complete" else "not_run",
                            manifest_verified=state == "complete"), "execution_host_id": "source-host"}

    def test_exact_repeat_and_fingerprint_only_resume(self):
        self.registry.append(self.record())
        self.assertEqual(self.registry.cell_status(self.plan, self.cell), "complete")
        self.assertEqual(self.registry.cell_status(self.plan, Cell("route1", "clear", 2)), "pending")
        self.config["mount_z_offset_m"] = 0.8
        write_json(self.root / "config.json", self.config)
        changed = fixture_plan(self.root)
        self.assertEqual(self.registry.cell_status(changed, self.cell), "pending")

    def test_expanded_matrix_resumes_only_unchanged_cells(self):
        self.registry.append(self.record())
        self.config["weather_profiles"]["rain"] = {"parameters": {"wetness": 90}}
        write_json(self.root / "config.json", self.config)
        expanded = fixture_plan(self.root)
        self.assertEqual(self.registry.cell_status(expanded, self.cell), "complete")
        self.assertEqual(self.registry.cell_status(expanded, Cell("route1", "rain", 1)), "pending")

    def test_v1_records_do_not_gain_unrecorded_measurement_identity(self):
        record = self.record()
        record["schema_version"] = 1
        record.pop("measurement_fingerprint")
        self.registry.append(record)
        self.assertEqual(self.registry.cell_status(self.plan, self.cell), "complete")
        self.config["weather_profiles"]["rain"] = {"parameters": {"wetness": 90}}
        write_json(self.root / "config.json", self.config)
        self.assertEqual(self.registry.cell_status(fixture_plan(self.root), self.cell), "pending")

    def test_running_unknown_block_failed_retry_and_latest_event(self):
        self.registry.append(self.record("running"))
        self.assertEqual(self.registry.cell_status(self.plan, self.cell), "blocked")
        self.registry.append(self.record("unknown"))
        self.assertEqual(self.registry.cell_status(self.plan, self.cell), "blocked")
        self.registry.append(self.record("failed"))
        self.assertEqual(self.registry.cell_status(self.plan, self.cell), "pending")
        self.assertEqual(len(self.registry.records()), 3)
        self.assertEqual(len(self.registry.latest()), 1)

    def test_new_vm_missing_data_requires_verified_export(self):
        record = self.registry.append(self.record())
        (self.run / "manifest.sha256").unlink()
        self.assertEqual(self.registry.cell_status(self.plan, self.cell), "unavailable")
        self.registry.append({**record, "external_copy": {"status": "user_reported", "location": "/mac/copy"}})
        self.assertEqual(self.registry.cell_status(self.plan, self.cell), "unavailable")
        self.registry.append({**record, "external_copy": {"status": "verified", "location": "/mac/copy", "evidence_path": "checks/copy.json",
                                                         "manifest_sha256": record["manifest_sha256"], "source_host_id": "source-host", "verification_host_id": "mac-host"}})
        self.assertEqual(self.registry.cell_status(self.plan, self.cell), "complete")

    def test_source_vm_copy_is_not_external_backup(self):
        record = self.record()
        external = {"status": "verified", "location": "/same-vm/copy", "evidence_path": "checks/copy.json",
                    "manifest_sha256": record["manifest_sha256"], "source_host_id": "source-host", "verification_host_id": "source-host"}
        with self.assertRaisesRegex(ValueError, "distinct execution and verification hosts"):
            self.registry.append({**record, "external_copy": external})

    def test_compact_allowlist_drops_environment_and_secrets(self):
        value = self.registry.append({**self.record(), "environment": {"API_KEY": "private"}, "api_key": "private"})
        self.assertNotIn("environment", value)
        self.assertNotIn("private", self.registry.path.read_text())
        self.assertEqual(value["external_copy"]["status"], "not_copied")

    def test_corrupt_registry_and_unverified_success_refused(self):
        value = self.record()
        value["finalization_verified"] = False
        with self.assertRaisesRegex(ValueError, "verified local manifest"):
            self.registry.append(value)
        self.registry.path.parent.mkdir(parents=True)
        self.registry.path.write_text('{"broken":')
        with self.assertRaisesRegex(ValueError, "invalid registry record"):
            self.registry.records()

    def finalize_fixture(self):
        write_json(self.run / "experiment_identity.json", self.plan.identity(self.cell))
        write_json(self.run / "experiment_manifest.json", self.plan.resolved_manifest)
        write_json(self.run / "metadata.json", {**self.plan.identity(self.cell), "state": "complete", "run_id": self.run.name,
                                              "execution_host_id": "source-host",
                                              "carla_client_version": "0.9.16", "carla_server_version": "0.9.16"})
        write_json(self.run / "baseline_config.json", {"route_id": self.cell.route_id, "weather_id": self.cell.weather_id})
        write_json(self.run / "baseline_validation.json", {"status": "passed"})
        entries = [f"{file_sha256(path)}  {path.stat().st_size}  {path.name}\n" for path in sorted(self.run.iterdir()) if path.name != "manifest.sha256"]
        (self.run / "manifest.sha256").write_text("".join(entries))

    def test_explicit_import_verifies_identity_and_files_without_backup_claim(self):
        self.finalize_fixture()
        imported = self.registry.import_run(self.run)
        self.assertEqual(imported["state"], "complete")
        self.assertEqual(imported["external_copy"]["status"], "unknown")
        (self.run / "baseline_validation.json").write_text('{"status":"failed"}')
        with self.assertRaisesRegex(ValueError, "hash/size mismatch"):
            self.registry.import_run(self.run)

    def test_import_refuses_legacy_without_assigning_current_identity(self):
        write_json(self.run / "metadata.json", {"state": "complete"})
        with self.assertRaisesRegex(ValueError, "legacy"):
            self.registry.import_run(self.run)
        self.assertEqual(self.registry.records(), [])

    def test_reimport_is_idempotent_and_preserves_external_proof(self):
        self.finalize_fixture()
        record = self.registry.import_run(self.run)
        self.registry.record_copy_check(self.run.name, {
            "status": "verified", "location": "/mac/copy", "evidence_path": "checks/copy.json",
            "manifest_sha256": record["manifest_sha256"], "source_host_id": "source-host", "verification_host_id": "mac-host"})
        count = len(self.registry.records())
        self.registry.import_run(self.run)
        self.assertEqual(len(self.registry.records()), count)
        (self.run / "manifest.sha256").unlink()
        self.assertEqual(self.registry.cell_status(self.plan, self.cell), "complete")

    def test_finalized_run_id_cannot_be_rebound(self):
        self.finalize_fixture()
        record = self.registry.import_run(self.run)
        with self.assertRaisesRegex(ValueError, "different identity"):
            self.registry.append({**record, "repeat_index": 2})
        # A self-consistent but changed run under an existing ID is also refused.
        write_json(self.run / "additional.json", {"changed": True})
        self.finalize_fixture()
        with self.assertRaisesRegex(ValueError, "change its manifest"):
            self.registry.import_run(self.run)


if __name__ == "__main__":
    unittest.main()
