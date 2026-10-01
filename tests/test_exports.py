import hashlib
import tempfile
import unittest
from pathlib import Path

from carla_tasks.exports import verify_export


class ExportTests(unittest.TestCase):
    def test_manifest_alone_can_verify_copy_without_source_images(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root / "manifest", root / "copy"
            source.mkdir()
            destination.mkdir()
            data = b"immutable sensor output"
            (destination / "image.png").write_bytes(data)
            (source / "manifest.sha256").write_text(f"{hashlib.sha256(data).hexdigest()}  {len(data)}  image.png\n")
            result = verify_export(source, destination)
            self.assertEqual(result["status"], "passed")
            (destination / "image.png").write_bytes(b"X" * len(data))
            self.assertEqual(verify_export(source, destination)["status"], "failed")

    def test_manifest_cannot_escape_destination_or_be_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.sha256"
            for relative in ("../outside", "/absolute"):
                manifest.write_text("a" * 64 + "  1  " + relative + "\n")
                with self.assertRaises(ValueError):
                    verify_export(root, root)
            manifest.write_text("")
            with self.assertRaises(ValueError):
                verify_export(root, root)
