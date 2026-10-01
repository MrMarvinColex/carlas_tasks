"""Bounded checks for active agent memory; never traverse datasets or raw chats."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import unquote

STARTUP_FILES = ("AGENTS.md", "docs/STATUS.md", "docs/PROJECT.md")
STARTUP_BUDGET_BYTES = 15 * 1024
ARCHIVE_FILES = {
    "AGENTS.snapshot.md", "README.md", "docs/STATUS.md", "docs/requirements.md",
    "docs/decisions.md", "docs/plan.md", "docs/knowledge.md", "docs/environment.md",
    "docs/runbook.md", "docs/worklog.md",
}


def check_docs(root: Path) -> dict[str, object]:
    root = root.resolve()
    errors: list[str] = []
    optional: list[str] = []
    total = 0
    for relative in STARTUP_FILES:
        path = root / relative
        if not path.is_file():
            errors.append(f"missing startup document: {relative}")
        else:
            total += path.stat().st_size
    if total > STARTUP_BUDGET_BYTES:
        errors.append(f"startup text exceeds {STARTUP_BUDGET_BYTES} bytes")
    files = [root / "AGENTS.md", root / "README.md", *sorted((root / "docs").glob("*.md"))]
    archive = root / "docs/archive/assignment-2026"
    files.append(archive / "index.md")
    checked = 0
    for file in files:
        if not file.is_file():
            continue
        for match in re.finditer(r"\[[^\]]*\]\(([^\)]+)\)", file.read_text()):
            target = match.group(1).strip().split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            if target.startswith("<"):
                target = target[1:target.index(">")]
            else:
                target = target.split(' "', 1)[0]
            target = re.sub(r":\d+$", "", unquote(target))
            resolved = (file.parent / target).resolve()
            checked += 1
            if not resolved.exists():
                if resolved.is_relative_to(root) and resolved.relative_to(root).parts[0] in {"runs", "logs", "logs_chats"}:
                    optional.append(target)
                else:
                    errors.append(f"{file.relative_to(root)}: missing local target {target}")
    manifest = archive / "manifest.sha256"
    archive_checked = 0
    archive_entries: set[str] = set()
    if not manifest.is_file():
        errors.append("missing historical archive manifest")
    else:
        for line in manifest.read_text().splitlines():
            try:
                digest, relative = line.split("  ", 1)
            except ValueError:
                errors.append("malformed historical archive manifest entry")
                continue
            if relative not in ARCHIVE_FILES or relative in archive_entries:
                errors.append(f"unexpected or duplicate historical snapshot: {relative}")
                continue
            archive_entries.add(relative)
            path = (archive / relative).resolve()
            if not path.is_relative_to(archive) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                errors.append(f"historical snapshot differs: {relative}")
            archive_checked += 1
        if archive_entries != ARCHIVE_FILES:
            errors.append("historical archive manifest must cover all ten original documents")
    if (archive / "AGENTS.md").exists():
        errors.append("historical AGENTS.md must be a non-discoverable snapshot")
    return {"valid": not errors, "startup_bytes": total, "startup_budget_bytes": STARTUP_BUDGET_BYTES,
            "checked_local_links": checked, "archive_files_verified": archive_checked,
            "optional_missing_evidence_links": optional, "errors": errors}
