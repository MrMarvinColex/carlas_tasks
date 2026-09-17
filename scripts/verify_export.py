#!/usr/bin/env python3
"""Verify an external copy against a source run manifest; it never copies or deletes files."""
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_run", type=Path)
    parser.add_argument("external_copy", type=Path)
    args = parser.parse_args()
    manifest = args.source_run / "manifest.sha256"
    if not manifest.is_file():
        raise SystemExit(f"missing source manifest: {manifest}")
    failures = []
    count = 0
    for line in manifest.read_text().splitlines():
        digest, size, relative = line.split("  ", 2)
        target = args.external_copy / relative
        if not target.is_file() or target.stat().st_size != int(size) or sha256(target) != digest:
            failures.append(relative)
        count += 1
    if failures:
        raise SystemExit(f"FAILED: {len(failures)}/{count} files differ or are missing: {', '.join(failures[:5])}")
    print(f"PASS: {count} files match {manifest}")


if __name__ == "__main__":
    main()
