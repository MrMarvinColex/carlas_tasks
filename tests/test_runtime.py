import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from carla_tasks.runtime import configure_synchronous_world, recorder_lock, restore_world_settings, validate_capture_timing


class World:
    def __init__(self):
        self.settings = SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=None,
                                        no_rendering_mode=True, substepping=True,
                                        max_substeps=10, max_substep_delta_time=0.01)
        self.ticks = 0

    def get_settings(self):
        return copy.copy(self.settings)

    def apply_settings(self, settings):
        self.settings = settings

    def tick(self):
        self.ticks += 1


class WorldTimingTests(unittest.TestCase):
    def test_requested_step_is_applied_and_original_state_restored(self):
        world = World()
        original = configure_synchronous_world(world, 0.025)
        self.assertEqual(world.settings.fixed_delta_seconds, 0.025)
        self.assertTrue(world.settings.synchronous_mode)
        self.assertEqual(world.ticks, 1)
        restore_world_settings(world, original)
        self.assertIsNone(world.settings.fixed_delta_seconds)
        self.assertFalse(world.settings.synchronous_mode)
        self.assertTrue(world.settings.no_rendering_mode)

    def test_invalid_steps_rejected_before_mutation(self):
        for step in (0, -1, float("nan"), 0.2):
            world = World()
            with self.assertRaises(ValueError):
                configure_synchronous_world(world, step)
            self.assertEqual(world.ticks, 0)

    def test_sensor_interval_must_align_to_world_ticks(self):
        validate_capture_timing(0.025, 0.5)
        with self.assertRaises(ValueError):
            validate_capture_timing(0.03, 0.5)

    def test_second_process_cannot_enter_active_recording(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recorder.lock"
            code = ("import sys; from pathlib import Path; from carla_tasks.runtime import recorder_lock, RecorderBusyError; "
                    "\ntry:\n with recorder_lock(Path(sys.argv[1])): print('started')"
                    "\nexcept RecorderBusyError: sys.exit(2)")
            with recorder_lock(path):
                blocked = subprocess.run([sys.executable, "-c", code, str(path)], capture_output=True, text=True)
            self.assertEqual(blocked.returncode, 2)
            self.assertEqual(blocked.stdout, "")
            allowed = subprocess.run([sys.executable, "-c", code, str(path)], capture_output=True, text=True)
            self.assertEqual(allowed.returncode, 0, allowed.stderr)
            self.assertEqual(allowed.stdout.strip(), "started")

    def test_lock_released_after_failed_recording(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recorder.lock"
            with self.assertRaisesRegex(RuntimeError, "failed capture"):
                with recorder_lock(path):
                    raise RuntimeError("failed capture")
            with recorder_lock(path):
                pass
