import json
import unittest
from pathlib import Path

from carla_tasks.experiments import DEFAULT_CALIBRATION
from carla_tasks.rigs import CameraSpec, Pose, RigSpec, resolve_av2_rig
from test_capture import tiny_rig

ROOT = Path(__file__).resolve().parents[1]


class RigTests(unittest.TestCase):
    def test_json_roundtrip_and_streams_follow_camera_count(self):
        for count in (1, 3, 9):
            rig = tiny_rig(count)
            self.assertEqual(RigSpec.from_dict(json.loads(json.dumps(rig.as_dict()))), rig)
            self.assertEqual(len(rig.streams), count * 2)
            self.assertEqual(rig.frame_stride(0.05), 2)

    def test_reject_ambiguous_or_unsupported_specs(self):
        rig = tiny_rig()
        with self.assertRaisesRegex(ValueError, "unique"):
            RigSpec("duplicate", (rig.cameras[0], rig.cameras[0]), 0.5)
        for changes in ({"projection": "fisheye"}, {"modalities": ["rgb"]}, {"coordinate_frame": "av2"}, {"typo": 1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                RigSpec.from_dict({**rig.as_dict(), **changes})
        with self.assertRaises(ValueError):
            CameraSpec("../escape", 1, 1, 90, Pose((0, 0, 0)))
        with self.assertRaises(ValueError):
            CameraSpec("bad", True, 1, 90, Pose((0, 0, 0)))
        with self.assertRaises(ValueError):
            Pose((float("nan"), 0, 0))

    def test_real_av2_calibration_uses_pure_adapter_with_explicit_vehicle_geometry(self):
        calibration = json.loads((ROOT / DEFAULT_CALIBRATION).read_text())
        rig, evidence = resolve_av2_rig(calibration, rig_id="av2-test", sensor_tick_seconds=0.5,
                                       rear_axle_origin_m=(-1.4, 0, 0.3), mount_z_offset_m=0.5,
                                       bbox_centre=(0, 0, 0.6), bbox_extent=(2.3, 1.0, 0.6))
        self.assertEqual(len(rig.streams), 18)
        for camera, check in zip(rig.cameras, evidence):
            self.assertEqual(camera.vehicle_from_camera.legacy_dict(), check["carla_relative_transform"])
            self.assertLess(check["numeric_checks"]["euler_roundtrip_max_error"], 1e-10)
            self.assertAlmostEqual(check["numeric_checks"]["rotation_determinant"], 1)
        with self.assertRaisesRegex(ValueError, "bounding box"):
            resolve_av2_rig(calibration, rig_id="bad", sensor_tick_seconds=0.5,
                            rear_axle_origin_m=(0, 0, 0), mount_z_offset_m=0,
                            bbox_centre=(0, 0, 0), bbox_extent=(100, 100, 100))
