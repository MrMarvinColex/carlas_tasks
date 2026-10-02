"""Verify a copied run from a small manifest; never transfer or delete data."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_export(source_run: Path, external_copy: Path) -> dict[str, object]:
    manifest = source_run / "manifest.sha256"
    if not manifest.is_file():
        raise ValueError(f"missing source manifest: {manifest}")
    destination = external_copy.resolve()
    failures: list[str] = []
    entries = 0
    seen: set[str] = set()
    for line in manifest.read_text().splitlines():
        digest, size, relative = line.split("  ", 2)
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or relative in seen:
            raise ValueError(f"unsafe or duplicate manifest path: {relative}")
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError(f"invalid SHA-256 for: {relative}")
        seen.add(relative)
        target = destination / path
        if not target.resolve().is_relative_to(destination):
            raise ValueError(f"manifest path escapes destination: {relative}")
        if not target.is_file() or target.stat().st_size != int(size) or sha256(target) != digest:
            failures.append(relative)
        entries += 1
    if not entries:
        raise ValueError("manifest contains no entries")
    return {"status": "passed" if not failures else "failed", "entries": entries,
            "failures": failures, "manifest_sha256": sha256(manifest),
            "external_location": str(destination)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_run", type=Path)
    parser.add_argument("external_copy", type=Path)
    args = parser.parse_args()
    result = verify_export(args.source_run, args.external_copy)
    if result["status"] != "passed":
        raise SystemExit(f"FAILED: {len(result['failures'])}/{result['entries']} files differ or are missing")
    print(f"PASS: {result['entries']} files match {args.source_run / 'manifest.sha256'}")
