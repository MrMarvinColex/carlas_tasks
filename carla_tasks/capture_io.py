"""Lossless, rig-driven reference writer for research-capture format v1.

This capture bundle is separate from legacy Stage-3/4 transforms. Experiment
finalization must additionally validate route/scene acceptance and sign a full
run manifest. A captured bundle alone must not satisfy a matrix cell.
"""
from __future__ import annotations

import json
import math
import os
import struct
import zlib
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .capture import CapturedSample, Snapshot
from .png import parse_png, write_grayscale_png, write_rgb_png
from .recording import CapturePolicy, PreparedSession
from .rigs import Pose, RigSpec


def _json(path: Path, value: Any) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


class CaptureDirectory:
    """Fresh output only; metadata commits are ordered by the recording thread."""
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=False)
        self.session: PreparedSession | None = None
        self.policy: CapturePolicy | None = None
        self.count = 0

    def begin(self, session: PreparedSession, policy: CapturePolicy) -> None:
        if self.session is not None:
            raise ValueError("capture sink already started")
        self.session, self.policy = session, policy
        _json(self.path / "rig.json", session.applied_rig.as_dict())
        _json(self.path / "capture_config.json", {"schema_version": 1, "format": "research-capture-v1",
              "policy": asdict(policy), "first_capture_frame": session.first_capture_frame,
              "initial_snapshot": asdict(session.initial_snapshot), "environment": session.evidence})
        (self.path / "samples.jsonl").touch(exist_ok=False)

    def write_sample(self, sample: CapturedSample) -> dict[str, Any]:
        if self.session is None:
            raise RuntimeError("capture sink has not started")
        expected = {stream.key: stream for stream in self.session.applied_rig.streams}
        if len(sample.images) != len(expected) or {packet.stream_key for packet in sample.images} != set(expected):
            raise ValueError("sample does not contain the declared stream set")
        images = {}
        for packet in sample.images:
            stream = expected[packet.stream_key]
            if (packet.frame != sample.snapshot.frame or abs(packet.simulation_time_s - sample.snapshot.simulation_time_s) > 1e-6
                    or (packet.width, packet.height) != (stream.width, stream.height)
                    or len(packet.bgra) != stream.width * stream.height * 4):
                raise ValueError("sample image does not match its snapshot or rig")
            relative = Path("images") / stream.camera_name / stream.modality / f"{packet.frame:010d}.png"
            path = self.path / relative
            if path.exists():
                raise ValueError("capture image already exists")
            if stream.modality == "semantic":
                write_grayscale_png(path, packet.width, packet.height, packet.bgra[2::4])
            else:
                pixels = bytearray(packet.width * packet.height * 3)
                pixels[0::3], pixels[1::3], pixels[2::3] = packet.bgra[2::4], packet.bgra[1::4], packet.bgra[0::4]
                write_rgb_png(path, packet.width, packet.height, bytes(pixels))
            images[packet.stream_key] = {"path": relative.as_posix(), "frame": packet.frame,
                                         "simulation_time_s": packet.simulation_time_s}
        return {"snapshot": asdict(sample.snapshot), "images": images}

    def commit_sample(self, record: dict[str, Any]) -> None:
        if self.session is None or self.policy is None:
            raise RuntimeError("capture sink has not started")
        expected = self.session.first_capture_frame + self.count * self.session.applied_rig.frame_stride(self.policy.fixed_delta_seconds)
        if record["snapshot"]["frame"] != expected or self.count >= self.policy.max_samples:
            raise ValueError("sample commit is out of order")
        with (self.path / "samples.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.count += 1

    def finalize(self, summary: dict[str, Any]) -> None:
        if self.policy is None or not 1 <= self.count <= self.policy.max_samples or summary["samples"] != self.count:
            raise ValueError("cannot finalize an incomplete capture")
        records = [json.loads(line) for line in (self.path / "samples.jsonl").read_text().splitlines()]
        if len(records) != self.count:
            raise ValueError("pose journal is incomplete")
        _json(self.path / "transforms.json", {"schema_version": 1, "samples": records})
        _json(self.path / "capture_result.json", summary)

    def abort(self, error: BaseException, cleanup_failures: list[dict[str, str]]) -> None:
        _json(self.path / "capture_failure.json", {"status": "failed", "committed_samples": self.count,
              "error_type": type(error).__name__, "reason": str(error), "cleanup_failures": cleanup_failures})


def validate_capture(path: Path) -> dict[str, Any]:
    """Full explicit validation, not a routine progress/status operation."""
    root = Path(path).resolve()
    if (root / "capture_failure.json").exists():
        raise ValueError("capture has failure evidence")
    rig = RigSpec.from_dict(json.loads((root / "rig.json").read_text()))
    config = json.loads((root / "capture_config.json").read_text())
    if config.get("format") != "research-capture-v1" or config.get("schema_version") != 1:
        raise ValueError("unsupported capture format")
    policy = CapturePolicy(**config["policy"])
    stride = rig.frame_stride(policy.fixed_delta_seconds)
    transforms = json.loads((root / "transforms.json").read_text())
    result = json.loads((root / "capture_result.json").read_text())
    records = transforms["samples"]
    journal = [json.loads(line) for line in (root / "samples.jsonl").read_text().splitlines()]
    if transforms.get("schema_version") != 1 or result.get("status") != "captured" or records != journal or not 1 <= len(records) <= policy.max_samples or result.get("samples") != len(records):
        raise ValueError("capture result and complete pose journal disagree")
    if result.get("termination") not in {"condition", "sample_limit"} or (result["termination"] == "sample_limit" and len(records) != policy.max_samples):
        raise ValueError("capture termination does not match its sample limit")
    streams = {stream.key: stream for stream in rig.streams}
    initial = config["initial_snapshot"]
    initial_snapshot = Snapshot(**{**initial, "world_from_vehicle": Pose(**initial["world_from_vehicle"])})
    if not initial_snapshot.frame < config["first_capture_frame"] <= initial_snapshot.frame + stride:
        raise ValueError("capture phase differs from initial snapshot")
    for index, record in enumerate(records):
        raw = record["snapshot"]
        snapshot = Snapshot(**{**raw, "world_from_vehicle": Pose(**raw["world_from_vehicle"])})
        expected_frame = config["first_capture_frame"] + index * stride
        expected_time = initial_snapshot.simulation_time_s + (expected_frame - initial_snapshot.frame) * policy.fixed_delta_seconds
        if snapshot.frame != expected_frame or not math.isclose(snapshot.simulation_time_s, expected_time, abs_tol=1e-6, rel_tol=0):
            raise ValueError("pose frame/time does not follow capture schedule")
        if set(record["images"]) != set(streams):
            raise ValueError("sample stream set differs from rig")
        for key, stream in streams.items():
            item = record["images"][key]
            expected_path = Path("images") / stream.camera_name / stream.modality / f"{expected_frame:010d}.png"
            image_path = (root / item["path"]).resolve()
            if item["path"] != expected_path.as_posix() or not image_path.is_relative_to(root):
                raise ValueError("unexpected or unsafe image path")
            if item["frame"] != snapshot.frame or not math.isclose(item["simulation_time_s"], snapshot.simulation_time_s, abs_tol=1e-6, rel_tol=0):
                raise ValueError("image metadata differs from pose frame/time")
            try:
                image = parse_png(image_path, include_pixels=stream.modality == "semantic")
            except (struct.error, zlib.error) as exc:
                raise ValueError(f"invalid PNG data: {expected_path}") from exc
            if (image["width"], image["height"], image["colour_type"]) != (stream.width, stream.height, 0 if stream.modality == "semantic" else 2):
                raise ValueError("PNG dimensions or encoding differ from rig")
    if result.get("first_frame") != config["first_capture_frame"] or result.get("last_frame") != records[-1]["snapshot"]["frame"] or result.get("frame_stride") != stride:
        raise ValueError("capture result frame range differs from samples")
    return {"status": "passed", "format": "research-capture-v1", "samples": len(records),
            "streams": len(streams), "images": len(records) * len(streams),
            "scope": "Capture integrity only; no route/scene acceptance, manifest or backup claim."}
