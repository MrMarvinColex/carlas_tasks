#!/usr/bin/env python3
"""Pure geometry helpers for the Stage-3 AV2-to-CARLA camera rig."""
from __future__ import annotations

import math
from typing import Iterable, Sequence


Matrix3 = list[list[float]]
Vector3 = tuple[float, float, float]


def matrix_multiply(first: Sequence[Sequence[float]], second: Sequence[Sequence[float]]) -> Matrix3:
    return [
        [sum(float(first[row][k]) * float(second[k][column]) for k in range(3)) for column in range(3)]
        for row in range(3)
    ]


def matrix_transpose(value: Sequence[Sequence[float]]) -> Matrix3:
    return [[float(value[column][row]) for column in range(3)] for row in range(3)]


def matrix_determinant(value: Sequence[Sequence[float]]) -> float:
    a, b, c = value[0]
    d, e, f = value[1]
    g, h, i = value[2]
    return float(a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g))


def matrix_vector(value: Sequence[Sequence[float]], vector: Sequence[float]) -> Vector3:
    return tuple(
        sum(float(value[row][column]) * float(vector[column]) for column in range(3))
        for row in range(3)
    )  # type: ignore[return-value]


def homogeneous_transform_point(matrix: Sequence[Sequence[float]], point: Sequence[float]) -> Vector3:
    if len(matrix) != 4 or any(len(row) != 4 for row in matrix) or len(point) != 3:
        raise ValueError("a 4x4 matrix and three-dimensional point are required")
    value = [float(point[0]), float(point[1]), float(point[2]), 1.0]
    transformed = [sum(float(matrix[row][column]) * value[column] for column in range(4)) for row in range(4)]
    if abs(transformed[3]) < 1e-12:
        raise ValueError("homogeneous point has zero scale")
    return tuple(component / transformed[3] for component in transformed[:3])  # type: ignore[return-value]


def max_identity_error(value: Sequence[Sequence[float]]) -> float:
    product = matrix_multiply(matrix_transpose(value), value)
    return max(
        abs(product[row][column] - (1.0 if row == column else 0.0))
        for row in range(3)
        for column in range(3)
    )


def quaternion_to_matrix(qw: float, qx: float, qy: float, qz: float) -> Matrix3:
    norm = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
    if norm <= 0.0:
        raise ValueError("quaternion has zero norm")
    w, x, y, z = (qw / norm, qx / norm, qy / norm, qz / norm)
    return [
        [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)],
        [2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)],
        [2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)],
    ]


def av2_camera_to_carla_actor_matrix(av2_sensor_to_ego: Sequence[Sequence[float]]) -> Matrix3:
    """Convert an AV2 optical-camera orientation into a CARLA actor orientation.

    AV2 ego is x-forward/y-left/z-up. CARLA is x-forward/y-right/z-up.
    AV2 optical axes are x-right/y-down/z-forward, whereas a CARLA camera
    actor uses x-forward/y-right/z-up.
    """
    av2_ego_to_carla_vehicle = [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]]
    carla_camera_to_av2_optical = [[0.0, 1.0, 0.0], [0.0, 0.0, -1.0], [1.0, 0.0, 0.0]]
    return matrix_multiply(
        matrix_multiply(av2_ego_to_carla_vehicle, av2_sensor_to_ego),
        carla_camera_to_av2_optical,
    )


def av2_translation_to_carla(value: Sequence[float], rear_axle_origin_m: Sequence[float]) -> Vector3:
    if len(value) != 3 or len(rear_axle_origin_m) != 3:
        raise ValueError("translations must contain three values")
    return (
        float(rear_axle_origin_m[0]) + float(value[0]),
        float(rear_axle_origin_m[1]) - float(value[1]),
        float(rear_axle_origin_m[2]) + float(value[2]),
    )


def matrix_to_carla_euler_deg(value: Sequence[Sequence[float]]) -> dict[str, float]:
    """Return CARLA roll/pitch/yaw for a 3x3 local-to-parent matrix."""
    pitch = math.asin(max(-1.0, min(1.0, float(value[2][0]))))
    cosine_pitch = math.cos(pitch)
    if abs(cosine_pitch) < 1e-8:
        yaw = math.atan2(-float(value[0][1]), float(value[1][1]))
        roll = 0.0
    else:
        yaw = math.atan2(float(value[1][0]), float(value[0][0]))
        roll = math.atan2(-float(value[2][1]), float(value[2][2]))
    return {
        "roll": math.degrees(roll),
        "pitch": math.degrees(pitch),
        "yaw": math.degrees(yaw),
    }


def carla_euler_to_matrix(roll: float, pitch: float, yaw: float) -> Matrix3:
    """Mirror the matrix convention used by carla.Rotation/get_matrix."""
    cr, sr = math.cos(math.radians(roll)), math.sin(math.radians(roll))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return [
        [cp * cy, cy * sp * sr - sy * cr, -cy * sp * cr - sy * sr],
        [cp * sy, sy * sp * sr + cy * cr, -sy * sp * cr + cy * sr],
        [sp, -cp * sr, cp * cr],
    ]


def horizontal_fov_deg(width_px: int, fx_px: float) -> float:
    if width_px <= 0 or fx_px <= 0.0:
        raise ValueError("width and focal length must be positive")
    return math.degrees(2.0 * math.atan(float(width_px) / (2.0 * fx_px)))


def rear_axle_midpoint_m(wheel_positions_cm: Iterable[Sequence[float]]) -> tuple[Vector3, list[Vector3]]:
    """Find the midpoint of the two rearmost wheels in CARLA local coordinates."""
    positions = [tuple(float(component) / 100.0 for component in value) for value in wheel_positions_cm]
    if len(positions) < 4 or any(len(value) != 3 for value in positions):
        raise ValueError("at least four three-dimensional wheel positions are required")
    ordered = sorted(positions, key=lambda value: value[0])
    rear = ordered[:2]
    front = ordered[-2:]
    if sum(value[0] for value in front) / 2.0 - sum(value[0] for value in rear) / 2.0 < 1.0:
        raise ValueError("wheelbase inferred from CARLA wheel positions is under one metre")
    midpoint = tuple(sum(value[index] for value in rear) / 2.0 for index in range(3))
    return midpoint, positions  # type: ignore[return-value]


def point_inside_box(point: Sequence[float], centre: Sequence[float], extent: Sequence[float]) -> bool:
    return all(abs(float(point[index]) - float(centre[index])) <= float(extent[index]) for index in range(3))


def ray_intersects_box(
    origin: Sequence[float], direction: Sequence[float], centre: Sequence[float], extent: Sequence[float]
) -> bool:
    """Return whether the positive ray enters an axis-aligned vehicle bounding box."""
    minimum = [float(centre[index]) - float(extent[index]) for index in range(3)]
    maximum = [float(centre[index]) + float(extent[index]) for index in range(3)]
    low, high = 0.0, float("inf")
    for index in range(3):
        component = float(direction[index])
        if abs(component) < 1e-12:
            if float(origin[index]) < minimum[index] or float(origin[index]) > maximum[index]:
                return False
            continue
        first = (minimum[index] - float(origin[index])) / component
        second = (maximum[index] - float(origin[index])) / component
        near, far = min(first, second), max(first, second)
        low, high = max(low, near), min(high, far)
        if high < low:
            return False
    return high >= max(low, 0.0)
