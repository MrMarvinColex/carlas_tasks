import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from stage3_geometry import (  # noqa: E402
    av2_camera_to_carla_actor_matrix,
    av2_translation_to_carla,
    carla_euler_to_matrix,
    horizontal_fov_deg,
    homogeneous_transform_point,
    matrix_determinant,
    matrix_to_carla_euler_deg,
    max_identity_error,
    point_inside_box,
    quaternion_to_matrix,
    ray_intersects_box,
    rear_axle_midpoint_m,
)


class Stage3GeometryTests(unittest.TestCase):
    def test_front_camera_conversion(self) -> None:
        rotation = quaternion_to_matrix(
            0.5028089058282348,
            -0.4996885698078901,
            0.5001474161095115,
            -0.4973400241104046,
        )
        converted = av2_camera_to_carla_actor_matrix(rotation)
        euler = matrix_to_carla_euler_deg(converted)
        rebuilt = carla_euler_to_matrix(**euler)
        self.assertAlmostEqual(matrix_determinant(converted), 1.0, places=10)
        self.assertLess(max_identity_error(converted), 1e-12)
        self.assertLess(max(abs(converted[r][c] - rebuilt[r][c]) for r in range(3) for c in range(3)), 1e-10)
        self.assertAlmostEqual(euler["yaw"], -0.287, places=2)

    def test_handedness_and_translation(self) -> None:
        converted = av2_translation_to_carla((1.5, 0.2, 1.4), (-1.4, 0.0, 0.3))
        for actual, expected in zip(converted, (0.1, -0.2, 1.7)):
            self.assertAlmostEqual(actual, expected)

    def test_fov(self) -> None:
        self.assertAlmostEqual(horizontal_fov_deg(1550, 1773.504271792515), 47.22, places=1)

    def test_rear_axle(self) -> None:
        midpoint, positions = rear_axle_midpoint_m(
            [(150, -80, -30), (150, 80, -30), (-140, -80, -30), (-140, 80, -30)]
        )
        self.assertEqual(len(positions), 4)
        self.assertEqual(midpoint, (-1.4, 0.0, -0.3))

    def test_homogeneous_transform_point(self) -> None:
        inverse_translation = [
            [1.0, 0.0, 0.0, -10.0],
            [0.0, 1.0, 0.0, 2.0],
            [0.0, 0.0, 1.0, -0.5],
            [0.0, 0.0, 0.0, 1.0],
        ]
        self.assertEqual(homogeneous_transform_point(inverse_translation, (11.0, 3.0, 1.5)), (1.0, 5.0, 1.0))

    def test_box_checks(self) -> None:
        self.assertTrue(point_inside_box((0, 0, 0), (0, 0, 0), (1, 1, 1)))
        self.assertFalse(point_inside_box((2, 0, 0), (0, 0, 0), (1, 1, 1)))
        self.assertTrue(ray_intersects_box((2, 0, 0), (-1, 0, 0), (0, 0, 0), (1, 1, 1)))
        self.assertFalse(ray_intersects_box((2, 0, 0), (1, 0, 0), (0, 0, 0), (1, 1, 1)))


if __name__ == "__main__":
    unittest.main()
