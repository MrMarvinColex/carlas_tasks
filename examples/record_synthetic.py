#!/usr/bin/env python3
"""Exercise the library on Mac. Synthetic pixels/poses are NOT CARLA evidence."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from carla_tasks.capture import FrameInbox, ImagePacket, Snapshot
from carla_tasks.capture_io import CaptureDirectory, validate_capture
from carla_tasks.recording import CapturePolicy, OwnedResources, PreparedSession, record
from carla_tasks.rigs import Pose, RigSpec


class SyntheticBackend:
    def prepare(self, resources: OwnedResources, requested_rig: RigSpec, policy: CapturePolicy) -> PreparedSession:
        self.rig, self.policy, self.frame = requested_rig, policy, 0
        self.stride = self.rig.frame_stride(policy.fixed_delta_seconds)
        return PreparedSession(self.snapshot(), self.stride, requested_rig,
                               {"backend": "synthetic-example", "is_carla_experiment": False})

    def listen(self, inbox: FrameInbox, resources: OwnedResources) -> None:
        self.inbox = inbox

    def snapshot(self) -> Snapshot:
        return Snapshot(self.frame, self.frame * self.policy.fixed_delta_seconds, Pose((self.frame * 0.1, 0, 0)))

    def advance(self) -> Snapshot:
        self.frame += 1
        current = self.snapshot()
        if self.frame % self.stride == 0:
            for index, stream in enumerate(reversed(self.rig.streams)):
                raw = bytes([index, self.frame % 256, 23 if stream.modality == "semantic" else 128, 255]) * (stream.width * stream.height)
                self.inbox.submit(ImagePacket(stream.key, self.frame, current.simulation_time_s, stream.width, stream.height, raw))
        return current


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rig", type=Path, default=Path("configs/rigs/three_camera_v1.json"))
    parser.add_argument("--output", type=Path, required=True, help="new directory, never an existing run")
    parser.add_argument("--samples", type=int, default=3)
    args = parser.parse_args()
    rig = RigSpec.from_dict(json.loads(args.rig.read_text()))
    summary = record(SyntheticBackend(), rig, CapturePolicy(args.samples), CaptureDirectory(args.output))
    print(json.dumps({"synthetic_only": True, "capture": summary, "validation": validate_capture(args.output)}, indent=2))


if __name__ == "__main__":
    main()
