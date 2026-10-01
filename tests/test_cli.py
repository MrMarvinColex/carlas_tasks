import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from carla_tasks.__main__ import main
from carla_tasks.registry import RunRegistry


class CliTests(unittest.TestCase):
    def call(self, argv):
        output = io.StringIO()
        with patch("sys.argv", ["carla_tasks", *argv]), contextlib.redirect_stdout(output):
            code = main()
        return code, json.loads(output.getvalue())

    def test_custom_rig_check_is_available_without_carla(self):
        code, result = self.call(["rig-check", "configs/rigs/three_camera_v1.json"])
        self.assertEqual(code, 0)
        self.assertEqual((result["cameras"], result["streams"], result["frame_stride"]), (3, 6, 2))

    def test_dataset_options_are_forwarded_before_positional_path(self):
        with patch("carla_tasks.dataset.main") as validate, patch(
            "sys.argv", ["carla_tasks", "validate-dataset", "--require-all-nine", "/tmp/example-run"]
        ):
            validate.side_effect = lambda: self.assertEqual(
                __import__("sys").argv, ["validate-dataset", "--require-all-nine", "/tmp/example-run"]
            )
            self.assertEqual(main(), 0)
            validate.assert_called_once()

    def make_copy(self, root):
        source, destination = root / "manifests", root / "external-run"
        source.mkdir()
        destination.mkdir()
        data = b"immutable sample"
        (destination / "data.bin").write_bytes(data)
        manifest = source / "manifest.sha256"
        manifest.write_text(f"{hashlib.sha256(data).hexdigest()}  {len(data)}  data.bin\n")
        registry = RunRegistry(root / "registry.jsonl")
        registry.append({"experiment_id": "example", "config_fingerprint": "a" * 64,
                         "run_id": "run-1", "route_id": "route1", "weather_id": "clear", "repeat_index": 1,
                         "state": "complete", "validation_status": "passed", "finalization_verified": True,
                         "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                         "execution_host_id": "source-host"})
        report = root / "checks/copy.json"
        argv = ["registry", "--path", str(registry.path), "verify-copy", "--run-id", "run-1",
                "--manifest-dir", str(source), "--copy", str(destination), "--report", str(report)]
        return registry, source, destination, report, argv

    def test_external_verification_updates_only_after_matching_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            registry, source, destination, report, argv = self.make_copy(Path(directory))
            with patch("carla_tasks.hosts.host_identity", return_value="mac-host"):
                code, result = self.call(argv)
            self.assertEqual(code, 0)
            self.assertEqual(result["status"], "passed")
            self.assertEqual(registry.latest()[0]["external_copy"]["status"], "verified")
            self.assertTrue(report.is_file())

    def test_same_origin_host_never_becomes_external_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            registry, source, destination, report, argv = self.make_copy(Path(directory))
            with patch("carla_tasks.hosts.host_identity", return_value="source-host"):
                code, result = self.call(argv)
            self.assertEqual(code, 2)
            self.assertEqual(registry.latest()[0]["external_copy"]["status"], "not_copied")
            self.assertFalse(report.exists())

    def test_corrupt_copy_retains_failed_evidence_and_unverified_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            registry, source, destination, report, argv = self.make_copy(Path(directory))
            (destination / "data.bin").write_bytes(b"different sample")
            with patch("carla_tasks.hosts.host_identity", return_value="mac-host"):
                code, result = self.call(argv)
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(report.read_text())["status"], "failed")
            self.assertEqual(registry.latest()[0]["external_copy"]["status"], "failed")

    def test_reverification_revokes_only_the_failed_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry, source, destination, report, argv = self.make_copy(root)
            with patch("carla_tasks.hosts.host_identity", return_value="mac-host"):
                self.assertEqual(self.call(argv)[0], 0)
                bad = root / "other-copy"
                bad.mkdir()
                other = list(argv)
                other[other.index("--copy") + 1] = str(bad)
                other[-1] = str(root / "other-check.json")
                self.assertEqual(self.call(other)[0], 1)
                self.assertEqual(registry.latest()[0]["external_copy"]["status"], "verified")
                self.assertEqual(registry.latest()[0]["last_copy_check"]["status"], "failed")
                (destination / "data.bin").write_bytes(b"corrupted")
                argv[-1] = str(root / "recheck.json")
                self.assertEqual(self.call(argv)[0], 1)
            self.assertEqual(registry.latest()[0]["external_copy"]["status"], "failed")

    def test_wait_timeout_unknown_and_failure_have_distinct_exit_codes(self):
        for state, outcome, expected in (("running", "timeout", 3), ("unknown", "unknown", 4),
                                         ("completed", "finished", 0), ("failed", "finished", 1)):
            with self.subTest(state=state), patch("carla_tasks.processes.wait_process", return_value={
                    "state": state, "wait_outcome": outcome}):
                code, result = self.call(["process", "wait", "--state", "unused.json"])
                self.assertEqual(code, expected)

    def test_different_source_manifest_is_rejected_without_new_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            registry, source, destination, report, argv = self.make_copy(Path(directory))
            # Keep the manifest parseable and its entries valid; only the signed
            # manifest bytes differ from the registry, so identity must reject it.
            (source / "manifest.sha256").write_text((source / "manifest.sha256").read_text().rstrip("\n"))
            with patch("carla_tasks.hosts.host_identity", return_value="mac-host"):
                code, result = self.call(argv)
            self.assertEqual(code, 2)
            self.assertFalse(report.exists())
