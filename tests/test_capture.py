import threading
import unittest

from carla_tasks.capture import CaptureError, FrameInbox, ImagePacket, Snapshot
from carla_tasks.rigs import CameraSpec, Pose, RigSpec


def tiny_rig(count=3):
    return RigSpec("test-rig", tuple(CameraSpec(f"camera{n}", 2, 1, 90, Pose((0, n, 2))) for n in range(count)), 0.1)


def snapshot(frame):
    return Snapshot(frame, frame * 0.05, Pose((frame, 0, 0)))


def packet(stream, frame_number, **overrides):
    return ImagePacket(**{"stream_key": stream.key, "frame": frame_number, "simulation_time_s": frame_number * 0.05,
                          "width": stream.width, "height": stream.height, "bgra": b"\x01\x02\x17\xff" * (stream.width * stream.height), **overrides})


class FrameInboxTests(unittest.TestCase):
    def inbox(self, count=2, **options):
        return FrameInbox(tiny_rig(), first_frame=2, stride=2, sample_count=count, **options)

    def test_reordered_callbacks_pair_same_frame_pose_and_detach_memory(self):
        inbox = self.inbox()
        mutable = bytearray(b"\x01\x02\x17\xff" * 2)
        detached = packet(tiny_rig().streams[0], 2, bgra=mutable)
        mutable[:] = b"\x00" * len(mutable)
        def deliver():
            for stream in reversed(tiny_rig().streams):
                inbox.submit(packet(stream, 4))
                inbox.submit(detached if stream == tiny_rig().streams[0] else packet(stream, 2))
        thread = threading.Thread(target=deliver)
        thread.start()
        try:
            first = inbox.take(snapshot(2), 1)
            second = inbox.take(snapshot(4), 1)
        finally:
            thread.join()
        self.assertEqual(first.snapshot.world_from_vehicle.location_m, (2, 0, 0))
        self.assertEqual(first.images[0].bgra[2], 23)
        self.assertEqual([p.frame for p in second.images], [4] * 6)
        inbox.assert_drained()

    def test_missing_all_streams_times_out_instead_of_skipping_frame(self):
        with self.assertRaisesRegex(CaptureError, "missing.*rgb:camera0"):
            self.inbox().take(snapshot(2), 0.001)

    def test_bad_packets_latch_failure_for_recording_thread(self):
        stream = tiny_rig().streams[0]
        cases = [({"stream_key": "rgb:unknown"}, "undeclared"), ({"frame": 3}, "schedule"),
                 ({"width": 99}, "dimensions"), ({"bgra": b"short"}, "length"),
                 ({"simulation_time_s": float("nan")}, "finite")]
        for overrides, message in cases:
            with self.subTest(message=message):
                inbox = self.inbox()
                inbox.submit(packet(stream, 2, **overrides))
                with self.assertRaisesRegex(CaptureError, message):
                    inbox.take(snapshot(2), 0.001)

    def test_duplicate_is_never_overwritten(self):
        inbox = self.inbox()
        for _ in range(2):
            inbox.submit(packet(tiny_rig().streams[0], 2))
        with self.assertRaisesRegex(CaptureError, "duplicate"):
            inbox.take(snapshot(2), 0.01)

    def test_timestamp_mismatch_is_not_paired_by_frame_alone(self):
        inbox = self.inbox()
        for stream in tiny_rig().streams:
            inbox.submit(packet(stream, 2, simulation_time_s=0.11))
        with self.assertRaisesRegex(CaptureError, "timestamp"):
            inbox.take(snapshot(2), 0.01)

    def test_overflow_and_callback_conversion_errors_are_visible(self):
        inbox = self.inbox(max_bytes=tiny_rig().sample_bytes)
        for stream in tiny_rig().streams:
            inbox.submit(packet(stream, 2))
        inbox.submit(packet(tiny_rig().streams[0], 4))
        with self.assertRaisesRegex(CaptureError, "buffer limit"):
            inbox.take(snapshot(2), 0.01)
        inbox = self.inbox()
        inbox.fail(ValueError("conversion failed"))
        with self.assertRaisesRegex(CaptureError, "callback failed"):
            inbox.take(snapshot(2), 0.01)

    def test_late_packet_after_consumption_still_invalidates_capture(self):
        inbox = self.inbox(count=1)
        for stream in tiny_rig().streams:
            inbox.submit(packet(stream, 2))
        inbox.take(snapshot(2), 0.01)
        inbox.submit(packet(tiny_rig().streams[0], 2))
        with self.assertRaisesRegex(CaptureError, "late/duplicate"):
            inbox.assert_drained()

    def test_wrong_snapshot_and_unsupported_cadence_rejected(self):
        with self.assertRaisesRegex(CaptureError, "expected snapshot"):
            self.inbox().take(snapshot(4), 0.01)
        with self.assertRaisesRegex(ValueError, "integer number"):
            tiny_rig().frame_stride(0.03)
