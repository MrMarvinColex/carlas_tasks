"""Lossless semantic PNG encoding independent of CARLA and image libraries."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

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


