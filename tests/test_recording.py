import json
import tempfile
import threading
import unittest
import struct
import zlib
from pathlib import Path

from carla_tasks.capture import CaptureError, FrameInbox, Snapshot
from carla_tasks.capture_io import CaptureDirectory, validate_capture
from carla_tasks.dataset import parse_png
from carla_tasks.recording import CapturePolicy, CleanupError, OwnedResources, PreparedSession, record
from test_capture import packet, snapshot, tiny_rig


class FakeBackend:
    """Deterministic test double, never presented as a CARLA experiment."""
    def __init__(self, *, mode="normal", initial=0):
        self.mode, self.frame = mode, initial
        self.events = []

    def prepare(self, resources, requested_rig, policy):
        self.rig = requested_rig
        resources.own("world-settings", lambda: self.events.append("restore-world"))
        resources.own("ego", lambda: self.events.append("destroy-ego"))
        if self.mode == "partial_setup":
            raise RuntimeError("spawn failed")
        if self.mode == "cleanup_failure":
            resources.own("bad-sensor", lambda: (_ for _ in ()).throw(RuntimeError("destroy failed")))
        return PreparedSession(snapshot(self.frame), self.frame + 2, requested_rig,
                               {"backend": "synthetic-test", "simulation_claim": False})

    def listen(self, inbox, resources):
        self.inbox = inbox
        resources.own("listeners", lambda: self.events.append("stop-listeners"))

    def advance(self):
        self.frame += 2 if self.mode == "frame_jump" else 1
        self.events.append(f"tick:{self.frame}")
        if self.mode == "interrupt":
            raise KeyboardInterrupt()
        if self.frame % 2 == 0:
            for stream in reversed(self.rig.streams):
                if self.mode == "missing" and stream == self.rig.streams[0]:
                    continue
                self.inbox.submit(packet(stream, self.frame))
        return snapshot(self.frame)


class RecordingTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def policy(self, **changes):
        return CapturePolicy(**{"max_samples": 3, "sensor_timeout_s": 0.01, **changes})

    def test_route_stop_ends_on_complete_sample_and_cap_is_distinct(self):
        sink = CaptureDirectory(self.root / "early-stop")
        summary = record(FakeBackend(), tiny_rig(), self.policy(max_samples=10), sink,
                         stop_after_sample=lambda pose: pose.frame >= 4)
        self.assertEqual((summary["samples"], summary["termination"]), (2, "condition"))
        self.assertEqual(validate_capture(sink.path)["samples"], 2)
        capped = CaptureDirectory(self.root / "capped")
        summary = record(FakeBackend(), tiny_rig(), self.policy(), capped, stop_after_sample=lambda pose: False)
        self.assertEqual(summary["termination"], "sample_limit")

    def test_one_and_three_and_nine_cameras_share_complete_pipeline(self):
        for count in (1, 3, 9):
            with self.subTest(cameras=count):
                backend = FakeBackend()
                path = self.root / f"rig-{count}"
                result = record(backend, tiny_rig(count), self.policy(), CaptureDirectory(path),
                                before_step=(lambda previous: backend.events.append(f"action:{previous.frame}"),))
                self.assertEqual(result["samples"], 3)
                self.assertEqual(backend.events[:4], ["action:0", "tick:1", "action:1", "tick:2"])
                self.assertEqual(backend.events[-3:], ["stop-listeners", "destroy-ego", "restore-world"])
                self.assertEqual(validate_capture(path)["images"], 3 * count * 2)
                semantic = path / "images/camera0/semantic/0000000002.png"
                self.assertEqual(parse_png(semantic, include_pixels=True)["_pixels"], bytes([23, 23]))
                rgb = (path / "images/camera0/rgb/0000000002.png").read_bytes()
                offset, compressed = 8, bytearray()
                while offset < len(rgb):
                    size = struct.unpack(">I", rgb[offset:offset + 4])[0]
                    if rgb[offset + 4:offset + 8] == b"IDAT":
                        compressed.extend(rgb[offset + 8:offset + 8 + size])
                    offset += 12 + size
                self.assertEqual(zlib.decompress(compressed), b"\x00\x17\x02\x01\x17\x02\x01")
                transforms = json.loads((path / "transforms.json").read_text())
                self.assertEqual([s["snapshot"]["frame"] for s in transforms["samples"]], [2, 4, 6])
                self.assertEqual(transforms["samples"][1]["snapshot"]["world_from_vehicle"]["location_m"], [4, 0, 0])

    def test_out_of_order_writer_finishes_commit_in_acquisition_order(self):
        second_finished = threading.Event()
        class ReorderedSink(CaptureDirectory):
            def write_sample(self, sample):
                if sample.snapshot.frame == 2:
                    if not second_finished.wait(2):
                        raise RuntimeError("second writer never ran")
                value = super().write_sample(sample)
                if sample.snapshot.frame == 4:
                    second_finished.set()
                return value
        # The first future may remain pending while the next sample is captured.
        sink = ReorderedSink(self.root / "reordered")
        result = record(FakeBackend(), tiny_rig(), self.policy(max_pending_writes=3), sink)
        self.assertGreaterEqual(result["peak_pending_writes"], 2)
        self.assertEqual(validate_capture(sink.path)["samples"], 3)

    def test_writer_byte_budget_reduces_queue_without_dropping_samples(self):
        rig = tiny_rig()
        sink = CaptureDirectory(self.root / "bounded")
        result = record(FakeBackend(), rig, self.policy(max_pending_writes=20, writer_buffer_bytes=rig.sample_bytes), sink)
        self.assertEqual(result["peak_pending_writes"], 1)
        self.assertEqual(validate_capture(sink.path)["samples"], 3)

    def test_setup_tick_missing_frame_cleanup_and_interrupt_failures_preserved(self):
        for mode, exception in (("partial_setup", RuntimeError), ("frame_jump", CaptureError),
                                ("missing", CaptureError), ("cleanup_failure", CleanupError), ("interrupt", KeyboardInterrupt)):
            with self.subTest(mode=mode):
                backend = FakeBackend(mode=mode)
                sink = CaptureDirectory(self.root / mode)
                with self.assertRaises(exception):
                    record(backend, tiny_rig(), self.policy(), sink)
                failure = json.loads((sink.path / "capture_failure.json").read_text())
                self.assertEqual(failure["status"], "failed")
                self.assertEqual(backend.events[-2:], ["destroy-ego", "restore-world"])
                self.assertFalse((sink.path / "transforms.json").exists())
                if mode == "cleanup_failure":
                    self.assertEqual(failure["cleanup_failures"][0]["resource"], "bad-sensor")

    def test_writer_failure_cannot_publish_complete_transforms(self):
        class BrokenSink(CaptureDirectory):
            def write_sample(self, sample):
                if sample.snapshot.frame == 4:
                    raise OSError("disk full")
                return super().write_sample(sample)
        backend = FakeBackend()
        sink = BrokenSink(self.root / "disk-failure")
        with self.assertRaisesRegex(OSError, "disk full"):
            record(backend, tiny_rig(), self.policy(), sink)
        self.assertFalse((sink.path / "transforms.json").exists())
        self.assertEqual(json.loads((sink.path / "capture_failure.json").read_text())["committed_samples"], 1)
        self.assertEqual(backend.events[-1], "restore-world")

    def test_cancel_and_primary_error_survive_cleanup_failure(self):
        backend = FakeBackend(mode="cleanup_failure")
        sink = CaptureDirectory(self.root / "cancelled")
        with self.assertRaises(InterruptedError) as caught:
            record(backend, tiny_rig(), self.policy(), sink, cancelled=lambda: True)
        self.assertEqual(caught.exception.cleanup_failures[0]["resource"], "bad-sensor")
        self.assertEqual(json.loads((sink.path / "capture_failure.json").read_text())["error_type"], "InterruptedError")

    def test_validation_rejects_corruption_and_incomplete_final_pose_file(self):
        sink = CaptureDirectory(self.root / "corrupt")
        record(FakeBackend(), tiny_rig(), self.policy(), sink)
        image = sink.path / "images/camera0/rgb/0000000002.png"
        image.write_bytes(b"broken")
        with self.assertRaisesRegex(ValueError, "PNG"):
            validate_capture(sink.path)
        path = sink.path / "transforms.json"
        value = json.loads(path.read_text())
        value["samples"].pop()
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "pose journal"):
            validate_capture(sink.path)

    def test_resource_cleanup_is_idempotent_and_cannot_silently_acquire_after_close(self):
        scope, events = OwnedResources(), []
        scope.own("one", lambda: events.append(1))
        scope.own("two", lambda: events.append(2))
        self.assertEqual(scope.close(), [])
        self.assertEqual(scope.close(), [])
        self.assertEqual(events, [2, 1])
        with self.assertRaises(RuntimeError):
            scope.own("late", lambda: None)
