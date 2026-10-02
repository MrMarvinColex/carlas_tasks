"""Bounded, fail-closed assembly of detached sensor packets and same-frame poses."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from .rigs import Pose, RigSpec, finite, positive_int


class CaptureError(RuntimeError):
    pass


@dataclass(frozen=True)
class Snapshot:
    frame: int
    simulation_time_s: float
    world_from_vehicle: Pose
    velocity_mps: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        if type(self.frame) is not int or self.frame < 0:
            raise ValueError("snapshot frame must be a nonnegative integer")
        finite(self.simulation_time_s, "simulation_time_s")
        if self.simulation_time_s < 0 or not isinstance(self.world_from_vehicle, Pose):
            raise ValueError("invalid snapshot time or pose")
        object.__setattr__(self, "velocity_mps", Pose(self.velocity_mps).location_m)


@dataclass(frozen=True)
class ImagePacket:
    """CARLA BGRA8 bytes: semantic class ID is the red byte, never a palette."""
    stream_key: str
    frame: int
    simulation_time_s: float
    width: int
    height: int
    bgra: bytes

    def __post_init__(self) -> None:
        # Detach simulator-owned memory before leaving the callback. No Image or
        # mutable bytearray is retained by capture or background writer threads.
        if not isinstance(self.bgra, (bytes, bytearray, memoryview)):
            raise ValueError("image buffer must be bytes-like")
        object.__setattr__(self, "bgra", bytes(self.bgra))


@dataclass(frozen=True)
class CapturedSample:
    snapshot: Snapshot
    images: tuple[ImagePacket, ...]


class FrameInbox:
    """Callbacks submit; the single recording thread takes scheduled frames.

    Never drop a packet to make room. Callback failures are latched and delivered
    to the recording thread even if the simulator swallows callback exceptions.
    The bound covers retained packets; at most one temporary packet per active
    producer can exist outside it. Writer memory has a separate explicit bound.
    """

    def __init__(self, rig: RigSpec, *, first_frame: int, stride: int, sample_count: int,
                 max_pending_frames: int = 2, max_bytes: int = 512 * 1024 * 1024,
                 timestamp_tolerance_s: float = 1e-6) -> None:
        for name, value in (("first_frame", first_frame), ("stride", stride), ("sample_count", sample_count),
                            ("max_pending_frames", max_pending_frames), ("max_bytes", max_bytes)):
            positive_int(value, name)
        finite(timestamp_tolerance_s, "timestamp tolerance")
        if timestamp_tolerance_s < 0 or max_bytes < rig.sample_bytes:
            raise ValueError("invalid tolerance or buffer cannot hold one complete sample")
        self.streams = {stream.key: stream for stream in rig.streams}
        self.first_frame, self.stride = first_frame, stride
        self.last_frame = first_frame + (sample_count - 1) * stride
        self.next_frame = first_frame
        self.max_pending_frames, self.max_bytes = max_pending_frames, max_bytes
        self.tolerance = timestamp_tolerance_s
        self._condition = threading.Condition()
        self._pending: dict[int, dict[str, ImagePacket]] = {}
        self._bytes = 0
        self.peak_bytes = 0
        self._error: CaptureError | None = None
        self._closed = False

    def fail(self, error: BaseException) -> None:
        with self._condition:
            if not self._closed and self._error is None:
                self._error = CaptureError(f"sensor callback failed: {type(error).__name__}: {error}")
            self._condition.notify_all()

    def submit(self, packet: ImagePacket) -> None:
        with self._condition:
            if self._closed or self._error:
                return
            try:
                self._insert(packet)
            except Exception as exc:
                self._error = CaptureError(str(exc))
            self._condition.notify_all()

    def _insert(self, packet: ImagePacket) -> None:
        if packet.stream_key not in self.streams:
            raise CaptureError(f"undeclared stream: {packet.stream_key}")
        if type(packet.frame) is not int or packet.frame < 0:
            raise CaptureError("invalid sensor frame")
        finite(packet.simulation_time_s, "sensor timestamp")
        if packet.frame < self.first_frame:
            return  # Explicit pre-recording warmup; never an accepted sample.
        if packet.frame < self.next_frame:
            raise CaptureError(f"late/duplicate packet for consumed frame {packet.frame}")
        if packet.frame > self.last_frame or (packet.frame - self.first_frame) % self.stride:
            raise CaptureError(f"sensor emitted outside declared schedule: {packet.frame}")
        stream = self.streams[packet.stream_key]
        if type(packet.width) is not int or type(packet.height) is not int or (packet.width, packet.height) != (stream.width, stream.height):
            raise CaptureError(f"dimensions differ for {packet.stream_key}")
        if len(packet.bgra) != stream.width * stream.height * 4:
            raise CaptureError(f"invalid BGRA buffer length for {packet.stream_key}")
        packets = self._pending.get(packet.frame, {})
        if packet.stream_key in packets:
            raise CaptureError(f"duplicate packet: {packet.frame}:{packet.stream_key}")
        if (packet.frame not in self._pending and len(self._pending) >= self.max_pending_frames) or self._bytes + len(packet.bgra) > self.max_bytes:
            raise CaptureError("sensor buffer limit exceeded; recording stopped without dropping data")
        self._pending.setdefault(packet.frame, {})[packet.stream_key] = packet
        self._bytes += len(packet.bgra)
        self.peak_bytes = max(self.peak_bytes, self._bytes)

    def take(self, snapshot: Snapshot, timeout_s: float) -> CapturedSample:
        finite(timeout_s, "sensor timeout")
        if timeout_s <= 0:
            raise ValueError("sensor timeout must be positive")
        with self._condition:
            if snapshot.frame != self.next_frame:
                raise CaptureError(f"expected snapshot {self.next_frame}, got {snapshot.frame}")
            deadline = time.monotonic() + timeout_s
            while True:
                self._check()
                packets = self._pending.get(snapshot.frame, {})
                if len(packets) == len(self.streams):
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    missing = sorted(self.streams.keys() - packets.keys())
                    raise CaptureError(f"frame {snapshot.frame} timed out; missing {missing}")
                self._condition.wait(remaining)
            ordered = tuple(packets[key] for key in self.streams)
            for packet in ordered:
                if abs(packet.simulation_time_s - snapshot.simulation_time_s) > self.tolerance:
                    raise CaptureError(f"timestamp differs from snapshot: {snapshot.frame}:{packet.stream_key}")
            del self._pending[snapshot.frame]
            self._bytes -= sum(len(packet.bgra) for packet in ordered)
            self.next_frame += self.stride
            return CapturedSample(snapshot, ordered)

    def _check(self) -> None:
        if self._error:
            raise self._error
        if self._closed:
            raise CaptureError("sensor inbox is closed")

    def assert_drained(self, *, last_frame: int | None = None) -> None:
        with self._condition:
            self._check()
            last = self.last_frame if last_frame is None else last_frame
            if last < self.first_frame or last > self.last_frame or (last - self.first_frame) % self.stride:
                raise CaptureError("invalid final capture frame")
            if self._pending or self.next_frame != last + self.stride:
                raise CaptureError("recording ended with unconsumed or missing samples")

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._pending.clear()
            self._bytes = 0
            self._condition.notify_all()
