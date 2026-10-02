import tempfile
import unittest
from pathlib import Path

from carla_tasks.maintenance import STARTUP_BUDGET_BYTES, check_docs

ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
    def test_actual_context_and_preserved_archive(self):
        result = check_docs(ROOT)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["archive_files_verified"], 10)

    def test_budget_and_links_fail_without_scanning_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs/archive/assignment-2026").mkdir(parents=True)
            (root / "docs/archive/assignment-2026/manifest.sha256").write_text("")
            (root / "AGENTS.md").write_text("x" * STARTUP_BUDGET_BYTES)
            (root / "docs/STATUS.md").write_text("[missing](missing.md)")
            (root / "docs/PROJECT.md").write_text("[optional](../runs/old.json)")
            result = check_docs(root)
            self.assertFalse(result["valid"])
            self.assertTrue(any("exceeds" in error for error in result["errors"]))
            self.assertTrue(any("missing local target" in error for error in result["errors"]))
            self.assertEqual(result["optional_missing_evidence_links"], ["../runs/old.json"])

    def test_malformed_or_shortened_archive_manifest_is_not_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs/archive/assignment-2026").mkdir(parents=True)
            for relative in ("AGENTS.md", "docs/STATUS.md", "docs/PROJECT.md"):
                (root / relative).write_text("small context")
            (root / "docs/archive/assignment-2026/manifest.sha256").write_text("broken entry\n")
            result = check_docs(root)
            self.assertFalse(result["valid"])
            self.assertTrue(any("malformed" in error for error in result["errors"]))
            self.assertTrue(any("all ten" in error for error in result["errors"]))
