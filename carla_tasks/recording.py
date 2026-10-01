"""One simulation clock, explicit ownership, bounded ordered background writing.

This is the reusable orchestration kernel. Backends alone translate simulator
objects; sinks alone encode datasets. Neither may advance simulation implicitly
after prepare() returns. Scene/route hooks run before each advance using the
previous snapshot. Captured data always uses the resulting frame's snapshot.
"""
from __future__ import annotations

import math
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from .capture import CapturedSample, CaptureError, FrameInbox, Snapshot
from .rigs import RigSpec, finite, positive_int


class CleanupError(RuntimeError):
    def __init__(self, failures: list[dict[str, str]]) -> None:
        super().__init__(f"owned-resource cleanup failed: {failures}")
        self.failures = failures


class OwnedResources:
    """Register immediately after acquisition; try every release in reverse order."""
    def __init__(self) -> None:
        self._callbacks: list[tuple[str, Callable[[], Any]]] = []
        self.failures: list[dict[str, str]] = []
        self.closed = False

    def own(self, name: str, release: Callable[[], Any]) -> None:
        if self.closed:
            raise RuntimeError("cannot acquire into a closed resource scope")
        self._callbacks.append((name, release))

    def close(self) -> list[dict[str, str]]:
        if not self.closed:
            self.closed = True
            while self._callbacks:
                name, release = self._callbacks.pop()
                try:
                    release()
                except BaseException as exc:
                    self.failures.append({"resource": name, "error_type": type(exc).__name__})
        return list(self.failures)


@dataclass(frozen=True)
class PreparedSession:
    initial_snapshot: Snapshot
    first_capture_frame: int
    applied_rig: RigSpec
    evidence: dict[str, Any]


class RecordingBackend(Protocol):
    def prepare(self, resources: OwnedResources, requested_rig: RigSpec, policy: CapturePolicy) -> PreparedSession:
        """Configure synchronous world, own actors, establish common sensor phase.

        Record actual versions, blueprint attributes, vehicle geometry, map and
        seed in evidence. Warmup is bounded and outside the recorded interval.
        All partially acquired actors/settings must already belong to resources.
        """
        ...

    def listen(self, inbox: FrameInbox, resources: OwnedResources) -> None:
        """Register callbacks without ticking; callback conversion errors call fail()."""
        ...

    def advance(self) -> Snapshot:
        """Advance exactly once, return snapshot and ego pose from that frame."""
        ...


class RecordingSink(Protocol):
    def begin(self, session: PreparedSession, policy: CapturePolicy) -> None: ...
    def write_sample(self, sample: CapturedSample) -> dict[str, Any]:
        """Worker-safe image write; return metadata, do not append the pose journal."""
        ...
    def commit_sample(self, record: dict[str, Any]) -> None:
        """Recording thread appends completed samples in acquisition order."""
        ...
    def finalize(self, summary: dict[str, Any]) -> None: ...
    def abort(self, error: BaseException, cleanup_failures: list[dict[str, str]]) -> None: ...


@dataclass(frozen=True)
class CapturePolicy:
    max_samples: int
    fixed_delta_seconds: float = 0.05
    sensor_timeout_s: float = 30.0
    writer_workers: int = 2
    max_pending_writes: int = 2
    max_pending_sensor_frames: int = 2
    sensor_buffer_bytes: int = 512 * 1024 * 1024
    writer_buffer_bytes: int = 512 * 1024 * 1024

    def __post_init__(self) -> None:
        for name in ("max_samples", "writer_workers", "max_pending_writes", "max_pending_sensor_frames",
                     "sensor_buffer_bytes", "writer_buffer_bytes"):
            positive_int(getattr(self, name), name)
        for name in ("fixed_delta_seconds", "sensor_timeout_s"):
            finite(getattr(self, name), name)
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")


class _OrderedWriter:
    def __init__(self, sink: RecordingSink, workers: int, limit: int) -> None:
        self.sink, self.limit = sink, limit
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="capture-writer")
        self.pending: deque[Future[dict[str, Any]]] = deque()
        self.count = 0
        self.peak_pending = 0

    def make_room(self) -> None:
        if len(self.pending) >= self.limit:
            self._commit_oldest()

    def submit(self, sample: CapturedSample) -> None:
        self.make_room()
        self.pending.append(self.pool.submit(self.sink.write_sample, sample))
        self.peak_pending = max(self.peak_pending, len(self.pending))

    def _commit_oldest(self) -> None:
        record = self.pending.popleft().result()
        self.sink.commit_sample(record)
        self.count += 1

    def finish(self) -> None:
        while self.pending:
            self._commit_oldest()

    def close(self) -> None:
        for future in self.pending:
            future.cancel()
        # Running writes must finish before failure evidence/finalization; Python
        # threads cannot be forcibly killed. Filesystem hangs need process control.
        self.pool.shutdown(wait=True, cancel_futures=True)
        self.pending.clear()


def record(backend: RecordingBackend, rig: RigSpec, policy: CapturePolicy, sink: RecordingSink, *,
           before_step: tuple[Callable[[Snapshot], None], ...] = (),
           stop_after_sample: Callable[[Snapshot], bool] | None = None,
           cancelled: Callable[[], bool] = lambda: False) -> dict[str, Any]:
    """Record up to max_samples, optionally stopping on a complete sample boundary.

    A route controller may request an earlier stop. Reaching the cap is reported
    separately and never implies route completion. Experiment acceptance remains
    the controller/validator's responsibility, recorded outside this kernel.
    """
    stride = rig.frame_stride(policy.fixed_delta_seconds)
    if min(policy.sensor_buffer_bytes, policy.writer_buffer_bytes) < rig.sample_bytes:
        raise ValueError("each buffer budget must hold at least one sample")
    write_limit = min(policy.max_pending_writes, policy.writer_buffer_bytes // rig.sample_bytes)
    resources = OwnedResources()
    inbox: FrameInbox | None = None
    writer: _OrderedWriter | None = None
    try:
        session = backend.prepare(resources, rig, policy)
        if session.applied_rig != rig:
            raise CaptureError("applied rig differs from requested rig; resolve adaptation explicitly before recording")
        previous = session.initial_snapshot
        if not previous.frame < session.first_capture_frame <= previous.frame + stride:
            raise CaptureError("backend must establish first capture phase within one sensor interval")
        inbox = FrameInbox(rig, first_frame=session.first_capture_frame, stride=stride,
                           sample_count=policy.max_samples, max_pending_frames=policy.max_pending_sensor_frames,
                           max_bytes=policy.sensor_buffer_bytes)
        sink.begin(session, policy)
        backend.listen(inbox, resources)
        writer = _OrderedWriter(sink, policy.writer_workers, write_limit)
        termination = "sample_limit"
        while previous.frame < inbox.last_frame:
            if cancelled():
                raise InterruptedError("recording cancelled")
            writer.make_room()  # Backpressure before advancing the world again.
            for action in before_step:
                action(previous)
            current = backend.advance()
            if current.frame != previous.frame + 1 or not math.isclose(
                    current.simulation_time_s - previous.simulation_time_s, policy.fixed_delta_seconds,
                    abs_tol=1e-6, rel_tol=0):
                raise CaptureError("world frame/time jumped; another ticker or wrong simulation step")
            if current.frame == inbox.next_frame:
                writer.submit(inbox.take(current, policy.sensor_timeout_s))
                if stop_after_sample is not None and stop_after_sample(current):
                    previous = current
                    termination = "condition"
                    break
            previous = current
        writer.finish()
        writer.close()
        failures = resources.close()  # Stop callbacks/destroy owned actors/restore settings.
        inbox.assert_drained(last_frame=previous.frame)
        if failures:
            raise CleanupError(failures)
        summary = {"status": "captured", "samples": writer.count, "first_frame": session.first_capture_frame,
                   "termination": termination,
                   "last_frame": previous.frame, "frame_stride": stride, "peak_sensor_bytes": inbox.peak_bytes,
                   "peak_pending_writes": writer.peak_pending,
                   "scope": "Capture only; experiment acceptance and export verification are separate."}
        sink.finalize(summary)
        return summary
    except BaseException as exc:
        failures = resources.close()
        if writer is not None:
            writer.close()
        try:
            sink.abort(exc, failures)
        except BaseException as evidence_error:
            # Keep the cause (including KeyboardInterrupt), expose evidence failure.
            exc.evidence_error = type(evidence_error).__name__
        exc.cleanup_failures = failures
        raise
    finally:
        if inbox is not None:
            inbox.close()
