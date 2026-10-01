import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
import stage4_batch as batch
from carla_tasks.registry import RunRegistry, run_record
from test_experiments import fixture, fixture_plan, write_json


class FakeRunner:
    commands = []
    startup_code = 0
    recorder_code = 0
    verify_code = 0
    startup_interrupt = False
    runtime_version = "0.9.16"

    def __init__(self, _path):
        self.active = None

    def write(self, _text):
        pass

    def interrupt_active(self):
        self.active = None

    def close(self):
        pass

    def run(self, command, *, env=None):
        self.commands.append(command)
        if command[0] == "bash":
            if command[1].endswith("run_carla.sh"):
                if self.startup_code == 0 and "--attach" not in command:
                    write_json(Path(env["CARLA_SERVER_LEASE"]), {"container_id": "owned-fixture"})
                    if self.startup_interrupt:
                        raise KeyboardInterrupt
                return self.startup_code
            return 0
        script = Path(command[1]).name
        if script == "create_run.py":
            run_dir = Path(command[command.index("--runs-dir") + 1]) / command[command.index("--run-id") + 1]
            write_json(run_dir / "metadata.json", {"state": "running"})
        elif script == "stage4_baseline.py":
            run_dir = Path(command[command.index("--run-dir") + 1])
            write_json(run_dir / "baseline_validation.json", {"status": "passed" if self.recorder_code == 0 else "failed"})
            write_json(run_dir / "metadata.json", {"state": "running", "carla_client_version": self.runtime_version, "carla_server_version": self.runtime_version})
            return self.recorder_code
        elif script == "finalize_run.py":
            run_dir = Path(command[2])
            write_json(run_dir / "metadata.json", {"state": command[command.index("--state") + 1]})
            (run_dir / "manifest.sha256").write_text("signed fixture manifest\n")
        elif script == "verify_export.py":
            return self.verify_code
        return 0


class BatchTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.config = fixture(self.root)
        self.plan = fixture_plan(self.root)
        self.registry = RunRegistry(self.root / "artifacts/run_registry.jsonl")
        FakeRunner.commands, FakeRunner.startup_code, FakeRunner.recorder_code, FakeRunner.verify_code = [], 0, 0, 0
        FakeRunner.startup_interrupt, FakeRunner.runtime_version = False, "0.9.16"

    def main(self, *args):
        with patch.object(batch, "ROOT", self.root), patch.object(batch, "RUNS_DIR", self.root / "runs"), \
             patch.object(batch, "LOGS_DIR", self.root / "logs"), patch.object(batch, "resolve_experiment", return_value=self.plan), \
             patch.object(batch, "CommandRunner", FakeRunner), patch.object(sys, "argv", ["batch", *args]), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return batch.main()

    def test_dry_run_on_clean_checkout_has_no_side_effects(self):
        with patch.object(Path, "iterdir", side_effect=AssertionError("must not scan output directories")):
            self.assertEqual(self.main("--dry-run"), 0)
        self.assertFalse((self.root / "runs").exists())
        self.assertFalse((self.root / "logs").exists())
        self.assertEqual(FakeRunner.commands, [])

    def test_repeats_executed_and_later_resume_does_not_run_again(self):
        self.config["repeats_per_route_weather"] = 2
        write_json(self.root / "config.json", self.config)
        self.plan = fixture_plan(self.root)
        self.assertEqual(self.main(), 0)
        self.assertEqual(len([cmd for cmd in FakeRunner.commands if len(cmd) > 1 and cmd[1].endswith("stage4_baseline.py")]), 2)
        self.assertEqual({row["repeat_index"] for row in self.registry.latest()}, {1, 2})
        self.assertTrue(all(row["external_copy"]["status"] == "not_copied" for row in self.registry.latest()))
        FakeRunner.commands = []
        self.assertEqual(self.main(), 0)
        self.assertEqual(FakeRunner.commands, [])

    def test_unknown_run_blocks_before_server_start(self):
        run = self.root / "runs/previous"
        self.registry.append(run_record(self.plan, self.plan.cells[0], run, "unknown"))
        self.assertEqual(self.main(), 2)
        self.assertEqual(FakeRunner.commands, [])

    def test_startup_failure_does_not_stop_an_unowned_server(self):
        FakeRunner.startup_code = 1
        self.assertEqual(self.main(), 1)
        self.assertEqual(FakeRunner.commands, [["bash", "scripts/run_carla.sh"]])
        self.assertFalse((self.root / "runs").exists())

    def test_explicit_healthy_attachment_does_not_stop_external_server(self):
        self.assertEqual(self.main("--attach-server"), 0)
        self.assertEqual(FakeRunner.commands[0], ["bash", "scripts/run_carla.sh", "--attach"])
        self.assertFalse(any(cmd[0] == "bash" and cmd[1].endswith("stop_carla.sh") for cmd in FakeRunner.commands))

    def test_failed_recorder_is_finalized_and_batch_stops(self):
        self.config["repeats_per_route_weather"] = 2
        write_json(self.root / "config.json", self.config)
        self.plan = fixture_plan(self.root)
        FakeRunner.recorder_code = 1
        self.assertEqual(self.main(), 1)
        self.assertEqual(len(self.registry.latest()), 1)
        self.assertEqual(self.registry.latest()[0]["state"], "failed")
        self.assertEqual(FakeRunner.commands[-1][:3], ["bash", "scripts/stop_carla.sh", "--lease"])

    def test_interruption_after_owned_lease_stops_exact_owned_container(self):
        FakeRunner.startup_interrupt = True
        self.assertEqual(self.main(), 130)
        self.assertEqual(FakeRunner.commands[-1][:3], ["bash", "scripts/stop_carla.sh", "--lease"])
        self.assertFalse((self.root / "runs").exists())

    def test_unplanned_client_or_server_version_cannot_be_registered_complete(self):
        FakeRunner.runtime_version = "0.9.15"
        self.assertEqual(self.main(), 1)
        self.assertEqual(self.registry.latest()[0]["state"], "failed")

    def test_local_verification_failure_cannot_be_registered_complete(self):
        FakeRunner.verify_code = 1
        self.assertEqual(self.main(), 1)
        self.assertEqual(self.registry.latest()[0]["state"], "failed")
        self.assertFalse(self.registry.latest()[0]["finalization_verified"])

    def test_input_drift_is_detected_without_running_carla(self):
        with patch.object(batch, "ROOT", self.root):
            batch.assert_identity_unchanged(self.plan)
            self.config["mount_z_offset_m"] = 0.9
            write_json(self.root / "config.json", self.config)
            with self.assertRaisesRegex(ValueError, "changed after planning"):
                batch.assert_identity_unchanged(self.plan)
        self.assertEqual(FakeRunner.commands, [])

    def test_post_recording_drift_is_finalized_failed_and_batch_stops(self):
        with patch.object(batch, "assert_identity_unchanged", side_effect=[None, ValueError("geometry changed after planning")]):
            self.assertEqual(self.main(), 1)
        record = self.registry.latest()[0]
        self.assertEqual(record["state"], "failed")
        self.assertEqual(record["validation_status"], "failed")
        finalize = next(cmd for cmd in FakeRunner.commands if len(cmd) > 1 and cmd[1].endswith("finalize_run.py"))
        self.assertIn("geometry changed after planning", finalize)


if __name__ == "__main__":
    unittest.main()
