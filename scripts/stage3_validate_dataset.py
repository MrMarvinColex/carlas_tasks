#!/usr/bin/env python3
"""Validate Stage-3 frame alignment, PNG integrity, dimensions, and timing."""
from __future__ import annotations

import argparse
import json
import shutil
import struct
import subprocess
import zlib
from pathlib import Path
from typing import Any


CAMERA_ORDER = (
    "ring_front_center",
    "ring_front_left",
    "ring_front_right",
    "ring_side_left",
    "ring_side_right",
    "ring_rear_left",
    "ring_rear_right",
    "stereo_front_left",
    "stereo_front_right",
)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def parse_png(path: Path, include_pixels: bool = False) -> dict[str, Any]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("invalid PNG signature")
    offset = 8
    width = height = bit_depth = colour_type = interlace = -1
    compressed = bytearray()
    saw_end = False
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("truncated PNG chunk")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        payload_end = offset + 8 + length
        crc_end = payload_end + 4
        if crc_end > len(data):
            raise ValueError("truncated PNG payload")
        payload = data[offset + 8 : payload_end]
        expected_crc = struct.unpack(">I", data[payload_end:crc_end])[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != expected_crc:
            raise ValueError(f"PNG CRC mismatch in {kind!r}")
        if kind == b"IHDR":
            width, height, bit_depth, colour_type, _, _, interlace = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            saw_end = True
            break
        offset = crc_end
    if not saw_end or width <= 0 or height <= 0 or not compressed:
        raise ValueError("PNG lacks required chunks")
    decoded = zlib.decompress(bytes(compressed))
    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(colour_type)
    if bit_depth != 8 or channels is None or interlace != 0:
        raise ValueError("validator supports non-interlaced 8-bit grayscale/RGB/RGBA PNG only")
    expected_decoded = height * (1 + width * channels)
    if len(decoded) != expected_decoded:
        raise ValueError(f"decoded PNG has {len(decoded)} bytes, expected {expected_decoded}")
    result: dict[str, Any] = {
        "width": width,
        "height": height,
        "bit_depth": bit_depth,
        "colour_type": colour_type,
        "bytes": len(data),
    }
    if include_pixels:
        if colour_type != 0:
            raise ValueError("pixel extraction is only supported for grayscale PNG")
        rows = []
        stride = width + 1
        for row in range(height):
            scanline = decoded[row * stride : (row + 1) * stride]
            if scanline[0] != 0:
                raise ValueError("raw semantic PNG unexpectedly uses a non-zero row filter")
            rows.append(scanline[1:])
        result["_pixels"] = b"".join(rows)
    return result


def make_contact_sheet(paths: list[Path], output: Path) -> dict[str, object]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return {"created": False, "reason": "ffmpeg not installed"}
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
    for path in paths:
        command.extend(["-i", str(path)])
    filters = []
    for index in range(9):
        filters.append(
            f"[{index}:v]scale=320:240:force_original_aspect_ratio=decrease,"
            f"pad=320:240:(ow-iw)/2:(oh-ih)/2:black[v{index}]"
        )
    filters.extend(
        [
            "[v0][v1][v2]hstack=inputs=3[row0]",
            "[v3][v4][v5]hstack=inputs=3[row1]",
            "[v6][v7][v8]hstack=inputs=3[row2]",
            "[row0][row1][row2]vstack=inputs=3[out]",
        ]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    command.extend(["-filter_complex", ";".join(filters), "-map", "[out]", "-frames:v", "1", str(output)])
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"created": False, "reason": str(exc)}
    return {"created": output.is_file(), "path": output.as_posix(), "camera_order": list(CAMERA_ORDER)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--interval-tolerance-s", type=float, default=0.0001)
    parser.add_argument("--require-all-nine", action="store_true")
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    checked_pngs = 0
    checked_bytes = 0
    maximum_ego_body_pixels_in_bottom_strip = 0
    try:
        transforms = json.loads((run_dir / "transforms.json").read_text())
        calibration = json.loads((run_dir / "calibration.json").read_text())
        summary = json.loads((run_dir / "capture_summary.json").read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read required Stage-3 JSON: {exc}")

    selected = list(summary.get("selected_camera_names", []))
    applied = {item["sensor_name"]: item for item in calibration.get("applied_cameras", [])}
    ego_semantic_tags = {
        int(tag) for tag in calibration.get("carla_vehicle", {}).get("semantic_tags_reported_by_actor", [])
    }
    if not ego_semantic_tags:
        errors.append("ego actor exposed no semantic tag for vehicle-body occlusion validation")
    if not selected or set(selected) != set(applied):
        errors.append("selected cameras and applied calibration differ")
    if args.require_all_nine and selected != list(CAMERA_ORDER):
        errors.append("full validation requires all nine AV2 cameras in canonical order")
    if int(summary.get("sensor_count", -1)) != len(selected) * 2:
        errors.append("sensor count is not two modalities per selected camera")
    if summary.get("duplicate_sensor_keys"):
        errors.append("duplicate sensor callbacks were recorded")
    for name, item in applied.items():
        checks = item.get("numeric_checks", {})
        if abs(float(checks.get("rotation_determinant", 0.0)) - 1.0) > 1e-9:
            errors.append(f"{name}: converted rotation determinant is not one")
        if float(checks.get("orthonormal_max_error", 1.0)) > 1e-9:
            errors.append(f"{name}: converted rotation is not orthonormal")
        if float(checks.get("euler_roundtrip_max_error", 1.0)) > 1e-9:
            errors.append(f"{name}: CARLA Euler conversion did not round-trip")
        if checks.get("origin_outside_vehicle_bbox") is not True:
            errors.append(f"{name}: camera origin intersects vehicle body")
        if checks.get("optical_axis_misses_vehicle_bbox") is not True:
            errors.append(f"{name}: camera optical axis intersects vehicle body")

    samples: list[dict[str, Any]] = transforms.get("samples", [])
    if transforms.get("state") != "complete" or not samples:
        errors.append("transforms.json is not a complete non-empty recording")
    if len(samples) != int(summary.get("sample_count", -1)):
        errors.append("sample count differs between transforms and capture summary")
    frames = [int(sample["frame"]) for sample in samples]
    timestamps = [float(sample["simulation_time_s"]) for sample in samples]
    sensor_timestamps = [float(sample["sensor_timestamp_s"]) for sample in samples]
    if frames != sorted(set(frames)):
        errors.append("frames are not unique and strictly increasing")
    if any(abs(first - second) > args.interval_tolerance_s for first, second in zip(timestamps, sensor_timestamps)):
        errors.append("sensor and ego snapshot timestamps differ")
    expected_interval = 1.0 / float(transforms.get("recording_frequency_hz", 0.0) or 0.0)
    if expected_interval <= 0.0:
        errors.append("invalid recording frequency")
    else:
        for previous, current in zip(sensor_timestamps, sensor_timestamps[1:]):
            if abs(current - previous - expected_interval) > args.interval_tolerance_s:
                errors.append(f"capture interval {current - previous:.9f}s differs from {expected_interval}s")

    first_rgb: list[Path] = []
    first_semantic: list[Path] = []
    for sample_index, sample in enumerate(samples):
        images = sample.get("images", {})
        if set(images) != set(selected):
            errors.append(f"sample {sample_index}: camera set differs from selected set")
            continue
        for camera_name in selected:
            expected_width = int(applied[camera_name]["image_width_px"])
            expected_height = int(applied[camera_name]["image_height_px"])
            paths = images[camera_name]
            expected_roles = {"rgb", "semantic_raw_ids", "semantic_preview"}
            if set(paths) != expected_roles:
                errors.append(f"sample {sample_index}/{camera_name}: output roles differ")
                continue
            for role, relative in paths.items():
                path = run_dir / relative
                if not path.is_file():
                    errors.append(f"missing {relative}")
                    continue
                try:
                    details = parse_png(path, include_pixels=role == "semantic_raw_ids")
                except (OSError, ValueError, zlib.error) as exc:
                    errors.append(f"invalid PNG {relative}: {exc}")
                    continue
                checked_pngs += 1
                checked_bytes += int(details["bytes"])
                if details["width"] != expected_width or details["height"] != expected_height:
                    errors.append(f"wrong dimensions for {relative}")
                if role == "semantic_raw_ids" and details["colour_type"] != 0:
                    errors.append(f"raw semantic IDs are not 8-bit grayscale in {relative}")
                if role == "semantic_raw_ids" and "_pixels" in details:
                    pixels = details.pop("_pixels")
                    bottom_rows = max(1, expected_height // 10)
                    bottom_strip = pixels[(expected_height - bottom_rows) * expected_width :]
                    ego_pixels = sum(value in ego_semantic_tags for value in bottom_strip)
                    maximum_ego_body_pixels_in_bottom_strip = max(
                        maximum_ego_body_pixels_in_bottom_strip, ego_pixels
                    )
                    if ego_pixels:
                        errors.append(
                            f"ego body occupies {ego_pixels} pixels in bottom 10% of {relative}"
                        )
                if role != "semantic_raw_ids" and details["colour_type"] not in {2, 6}:
                    errors.append(f"colour output has unexpected PNG type in {relative}")
            if sample_index == 0:
                first_rgb.append(run_dir / paths["rgb"])
                first_semantic.append(run_dir / paths["semantic_preview"])

    expected_pngs = len(samples) * len(selected) * 3
    if checked_pngs != expected_pngs:
        errors.append(f"validated {checked_pngs} PNG files, expected {expected_pngs}")
    expected_sensor_images = len(samples) * len(selected) * 2
    if int(summary.get("image_count", -1)) != expected_sensor_images:
        errors.append("reported RGB+raw-semantic image count is incorrect")

    contact_sheets: dict[str, object] = {}
    if selected == list(CAMERA_ORDER) and len(first_rgb) == 9:
        contact_sheets["rgb"] = make_contact_sheet(first_rgb, run_dir / "previews" / "contact_sheet_rgb.png")
        contact_sheets["semantic"] = make_contact_sheet(
            first_semantic, run_dir / "previews" / "contact_sheet_semantic.png"
        )
        if not all(item.get("created") for item in contact_sheets.values()):
            warnings.append("one or more contact sheets could not be generated")

    validation = {
        "status": "passed" if not errors else "failed",
        "interval_tolerance_s": args.interval_tolerance_s,
        "checks": {
            "json_parseable": True,
            "selected_camera_count": len(selected),
            "sensor_count": int(summary.get("sensor_count", -1)),
            "sample_count": len(samples),
            "unique_increasing_frames": frames == sorted(set(frames)),
            "same_frame_pose_and_sensor_timestamps": not any(
                abs(first - second) > args.interval_tolerance_s
                for first, second in zip(timestamps, sensor_timestamps)
            ),
            "validated_png_count": checked_pngs,
            "expected_png_count_including_previews": expected_pngs,
            "validated_png_bytes": checked_bytes,
            "maximum_ego_body_pixels_in_bottom_strip": maximum_ego_body_pixels_in_bottom_strip,
            "raw_semantic_encoding": "PNG grayscale, 8 bits, each value is the unmodified CARLA R-channel class ID",
        },
        "contact_sheets": contact_sheets,
        "errors": errors,
        "warnings": warnings,
    }
    write_json(run_dir / "validation.json", validation)
    print(run_dir / "validation.json")
    if errors:
        raise SystemExit(f"FAILED: {len(errors)} validation errors; see {run_dir / 'validation.json'}")


if __name__ == "__main__":
    main()
