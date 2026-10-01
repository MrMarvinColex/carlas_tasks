import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from carla_tasks.processes import read_status, start_process, wait_process

ROOT = Path(__file__).resolve().parents[1]


class SupervisionTests(unittest.TestCase):
    def test_timeout_does_not_turn_pending_into_success(self):
        with patch("carla_tasks.processes.read_status", return_value={"state": "running", "exit_code": None}), patch(
                "carla_tasks.processes.time.monotonic", side_effect=[0, 2]):
            status = wait_process(Path("unused"), 1)
        self.assertEqual(status["state"], "running")
        self.assertEqual(status["wait_outcome"], "timeout")

    def test_child_survives_launcher_exit_and_has_explicit_exit_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state, log = root / "state.json", root / "child.log"
            result = subprocess.run(
                [sys.executable, "-m", "carla_tasks", "process", "start", "--state", str(state),
                 "--log", str(log), "--", sys.executable, "-c", "import time; time.sleep(.5); print('done')"],
                cwd=ROOT, capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            status = wait_process(state, 5)
            self.assertEqual(status["state"], "completed")
            self.assertEqual(status["exit_code"], 0)
            self.assertEqual(log.read_text().strip(), "done")

    def test_duplicate_attempt_refused_even_after_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state, log = root / "state.json", root / "child.log"
            start_process([sys.executable, "-c", "pass"], state, log, ROOT)
            wait_process(state, 5)
            with self.assertRaises(FileExistsError):
                start_process([sys.executable, "-c", "pass"], state, root / "second.log", ROOT)
            self.assertFalse((root / "second.log").exists())

    def test_nonzero_exit_is_retained_without_command_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state.json"
            start_process([sys.executable, "-c", "import sys; sys.exit(7)", "private-argument"],
                          state, root / "child.log", ROOT)
            status = wait_process(state, 5)
            self.assertEqual(status["state"], "failed")
            self.assertEqual(status["exit_code"], 7)
            self.assertNotIn("private-argument", state.read_text())

    def test_missing_supervisor_is_unknown_not_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            state.write_text(json.dumps({"state": "running", "supervisor_pid": 2147483647}))
            observed = read_status(state)
            self.assertEqual(observed["state"], "running")
            self.assertIn("unknown", observed["observation"])

    def test_missing_program_produces_terminal_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state.json"
            start_process([str(root / "absent")], state, root / "child.log", ROOT)
            status = wait_process(state, 5)
            self.assertEqual(status["state"], "failed")
            self.assertEqual(status["error"], "FileNotFoundError")
