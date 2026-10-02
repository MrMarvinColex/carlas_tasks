"""Small recorder progress files replace repeated image-directory scans."""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path


def write_progress(run_dir: Path, phase: str, **fields: object) -> None:
    value = {"schema_version": 1, "run_id": run_dir.name, "phase": phase,
             "updated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), **fields}
    temporary = run_dir / f".progress-{os.getpid()}.tmp"
    temporary.write_text(json.dumps(value, sort_keys=True) + "\n")
    temporary.replace(run_dir / "progress.json")
