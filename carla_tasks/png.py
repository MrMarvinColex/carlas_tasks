"""Lossless semantic PNG encoding independent of CARLA and image libraries."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Any

def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def write_grayscale_png(path: Path, width: int, height: int, pixels: bytes) -> None:
    """Write unmodified 8-bit class IDs without an image-library dependency."""
    if len(pixels) != width * height:
        raise ValueError(f"raw semantic buffer has {len(pixels)} bytes, expected {width * height}")
    scanlines = b"".join(b"\x00" + pixels[row * width : (row + 1) * width] for row in range(height))
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(scanlines, level=6))
        + png_chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def write_rgb_png(path: Path, width: int, height: int, pixels: bytes) -> None:
    if len(pixels) != width * height * 3:
        raise ValueError(f"RGB buffer has {len(pixels)} bytes, expected {width * height * 3}")
    scanlines = b"".join(b"\x00" + pixels[row * width * 3 : (row + 1) * width * 3] for row in range(height))
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(scanlines, level=6))
        + png_chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


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
