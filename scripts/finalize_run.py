#!/usr/bin/env python3
"""Write a manifest and mark one local run complete or failed after validation."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--state", choices=("complete", "failed", "incomplete"), required=True)
    parser.add_argument("--reason", default="")
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.is_file():
        raise SystemExit(f"missing metadata: {metadata_path}")

    metadata = json.loads(metadata_path.read_text())
    # The manifest signs metadata, so its own checksum belongs in the registry,
    # not in this signed file. Remove values written by early script revisions.
    metadata.pop("manifest_sha256", None)
    metadata.pop("bytes_excluding_manifest", None)
    metadata.update({
        "state": args.state,
        "finalized_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "validation": {"status": "passed" if args.state == "complete" else "failed", "reason": args.reason},
    })
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    entries = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_file() and path.name != "manifest.sha256":
            relative = path.relative_to(run_dir).as_posix()
            entries.append((relative, path.stat().st_size, file_sha256(path)))
    manifest = "".join(f"{digest}  {size}  {relative}\n" for relative, size, digest in entries)
    manifest_path = run_dir / "manifest.sha256"
    manifest_path.write_text(manifest)
    print(manifest_path)


if __name__ == "__main__":
    main()
