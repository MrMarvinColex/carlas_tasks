"""Offline, versioned camera contracts. All poses use CARLA axes, metres/degrees.

Version 1 supports perspective cameras with paired RGB/semantic BGRA8 sources,
one common cadence, zero lens distortion and lossless PNG output. No CARLA import.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from .camera_geometry import (
    av2_camera_to_carla_actor_matrix, av2_translation_to_carla, carla_euler_to_matrix,
    horizontal_fov_deg, matrix_determinant, matrix_to_carla_euler_deg,
    max_identity_error, point_inside_box, quaternion_to_matrix, ray_intersects_box,
)
from .experiments import validate_identifier


def finite(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def positive_int(value: int, name: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class Pose:
    """Local-to-parent pose: x forward, y right, z up; roll/pitch/yaw degrees."""
    location_m: tuple[float, float, float]
    rotation_deg: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        for name in ("location_m", "rotation_deg"):
            vector = tuple(getattr(self, name))
            if len(vector) != 3:
                raise ValueError(f"{name} must have three components")
            for value in vector:
                finite(value, name)
            object.__setattr__(self, name, vector)

    def legacy_dict(self) -> dict[str, Any]:
        return {"location": dict(zip(("x", "y", "z"), self.location_m)),
                "rotation": dict(zip(("roll", "pitch", "yaw"), self.rotation_deg))}


@dataclass(frozen=True)
class CameraSpec:
    name: str
    width: int
    height: int
    horizontal_fov_deg: float
    vehicle_from_camera: Pose

    def __post_init__(self) -> None:
        validate_identifier(self.name, "camera name")
        positive_int(self.width, "width")
        positive_int(self.height, "height")
        finite(self.horizontal_fov_deg, "horizontal_fov_deg")
        if not 0 < self.horizontal_fov_deg < 180:
            raise ValueError("horizontal_fov_deg must lie between 0 and 180")
        if not isinstance(self.vehicle_from_camera, Pose):
            raise ValueError("camera transform must be a Pose")


@dataclass(frozen=True)
class StreamSpec:
    key: str
    camera_name: str
    modality: str
    width: int
    height: int


@dataclass(frozen=True)
class RigSpec:
    rig_id: str
    cameras: tuple[CameraSpec, ...]
    sensor_tick_seconds: float

    def __post_init__(self) -> None:
        validate_identifier(self.rig_id, "rig_id")
        object.__setattr__(self, "cameras", tuple(self.cameras))
        if not self.cameras or any(not isinstance(camera, CameraSpec) for camera in self.cameras):
            raise ValueError("rig requires camera specifications")
        if len({camera.name for camera in self.cameras}) != len(self.cameras):
            raise ValueError("camera names must be unique")
        finite(self.sensor_tick_seconds, "sensor_tick_seconds")
        if self.sensor_tick_seconds <= 0:
            raise ValueError("sensor cadence must be positive")

    @property
    def streams(self) -> tuple[StreamSpec, ...]:
        return tuple(StreamSpec(f"{modality}:{c.name}", c.name, modality, c.width, c.height)
                     for c in self.cameras for modality in ("rgb", "semantic"))

    @property
    def sample_bytes(self) -> int:
        return sum(stream.width * stream.height * 4 for stream in self.streams)

    def frame_stride(self, fixed_delta_seconds: float) -> int:
        finite(fixed_delta_seconds, "fixed_delta_seconds")
        if fixed_delta_seconds <= 0:
            raise ValueError("simulation step must be positive")
        ratio = self.sensor_tick_seconds / fixed_delta_seconds
        stride = round(ratio)
        if stride < 1 or not math.isclose(ratio, stride, abs_tol=1e-8, rel_tol=0):
            raise ValueError("sensor cadence must be an integer number of simulation steps")
        return stride

    def as_dict(self) -> dict[str, Any]:
        return {"schema_version": 1, "coordinate_frame": "carla_vehicle",
                "projection": "perspective", "modalities": ["rgb", "semantic"], **asdict(self)}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> RigSpec:
        required = {"schema_version", "coordinate_frame", "projection", "modalities", "rig_id", "cameras", "sensor_tick_seconds"}
        if not isinstance(value, dict) or set(value) != required or type(value["schema_version"]) is not int or value["schema_version"] != 1:
            raise ValueError("unsupported rig schema or fields")
        if value["coordinate_frame"] != "carla_vehicle" or value["projection"] != "perspective" or value["modalities"] != ["rgb", "semantic"]:
            raise ValueError("v1 requires CARLA vehicle poses and paired perspective RGB/semantic")
        try:
            cameras = tuple(CameraSpec(**{**camera, "vehicle_from_camera": Pose(**camera["vehicle_from_camera"])})
                            for camera in value["cameras"])
            return cls(value["rig_id"], cameras, value["sensor_tick_seconds"])
        except (KeyError, TypeError) as exc:
            raise ValueError("invalid camera specification") from exc


def resolve_av2_camera(camera: dict[str, Any], rear_axle_origin_m: tuple[float, float, float],
                       mount_z_offset_m: float, bbox_centre: tuple[float, float, float],
                       bbox_extent: tuple[float, float, float]) -> tuple[CameraSpec, dict[str, Any]]:
    """Pure AV2 adaptation given measured vehicle geometry, with old evidence shape.

    Live code must supply actual rear-axle/bounding-box measurements and preserve
    their provenance. Passing synthetic geometry is only an offline calculation.
    """
    finite(mount_z_offset_m, "mount_z_offset_m")
    for vector in (rear_axle_origin_m, bbox_centre, bbox_extent):
        Pose(vector)
    if any(component <= 0 for component in bbox_extent):
        raise ValueError("bounding-box extents must be positive")
    extrinsic = camera["egovehicle_SE3_sensor"]
    values = [extrinsic[key] for key in ("qw", "qx", "qy", "qz", "tx_m", "ty_m", "tz_m")]
    for value in values:
        finite(value, "AV2 extrinsic")
    actor_matrix = av2_camera_to_carla_actor_matrix(quaternion_to_matrix(*values[:4]))
    euler = matrix_to_carla_euler_deg(actor_matrix)
    rebuilt = carla_euler_to_matrix(**euler)
    location = list(av2_translation_to_carla(values[4:], rear_axle_origin_m))
    location[2] += mount_z_offset_m
    pose = Pose(tuple(location), tuple(euler[key] for key in ("roll", "pitch", "yaw")))
    intrinsics = camera["intrinsics"]
    for key in ("fx_px", "cx_px", "cy_px"):
        finite(intrinsics[key], key)
    width, height = intrinsics["width_px"], intrinsics["height_px"]
    fov = horizontal_fov_deg(width, intrinsics["fx_px"])
    specification = CameraSpec(camera["sensor_name"], width, height, fov, pose)
    forward = tuple(actor_matrix[index][0] for index in range(3))
    inside = point_inside_box(location, bbox_centre, bbox_extent)
    intersects = ray_intersects_box(location, forward, bbox_centre, bbox_extent)
    if inside or intersects:
        raise ValueError(f"{specification.name} origin or optical axis intersects the vehicle bounding box")
    return specification, {
        "sensor_name": specification.name, "raw_av2": camera,
        "carla_relative_transform": pose.legacy_dict(),
        "carla_local_to_vehicle_rotation_matrix": actor_matrix,
        "carla_camera_forward_axis_in_vehicle": list(forward), "horizontal_fov_deg": fov,
        "image_width_px": width, "image_height_px": height,
        "principal_point_offset_from_image_centre_px": {"x": intrinsics["cx_px"] - width / 2, "y": intrinsics["cy_px"] - height / 2},
        "numeric_checks": {"rotation_determinant": matrix_determinant(actor_matrix),
                           "orthonormal_max_error": max_identity_error(actor_matrix),
                           "euler_roundtrip_max_error": max(abs(actor_matrix[r][c] - rebuilt[r][c]) for r in range(3) for c in range(3)),
                           "origin_outside_vehicle_bbox": True, "optical_axis_misses_vehicle_bbox": True},
        "projection_limits": "CARLA receives AV2 width/height and the horizontal FOV derived from fx. "
                             "CARLA 0.9.16 cannot set AV2 cx/cy or the full k1/k2/k3 model; distortion is disabled.",
    }


def resolve_av2_rig(calibration: dict[str, Any], *, rig_id: str, sensor_tick_seconds: float,
                    rear_axle_origin_m: tuple[float, float, float], mount_z_offset_m: float,
                    bbox_centre: tuple[float, float, float], bbox_extent: tuple[float, float, float]) -> tuple[RigSpec, list[dict[str, Any]]]:
    resolved = [resolve_av2_camera(camera, rear_axle_origin_m, mount_z_offset_m, bbox_centre, bbox_extent)
                for camera in calibration["cameras"]]
    return (RigSpec(rig_id, tuple(camera for camera, _ in resolved), sensor_tick_seconds),
            [evidence for _, evidence in resolved])
