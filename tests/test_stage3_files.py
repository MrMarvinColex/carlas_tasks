import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from stage3_recording import CAMERA_ORDER, write_grayscale_png  # noqa: E402
from stage3_validate_dataset import parse_png  # noqa: E402


class Stage3FileTests(unittest.TestCase):
    def test_raw_semantic_png_roundtrip_structure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "classes.png"
            write_grayscale_png(path, 3, 2, bytes([0, 1, 24, 14, 7, 255]))
            details = parse_png(path, include_pixels=True)
            self.assertEqual(details["width"], 3)
            self.assertEqual(details["height"], 2)
            self.assertEqual(details["bit_depth"], 8)
            self.assertEqual(details["colour_type"], 0)
            self.assertEqual(details["_pixels"], bytes([0, 1, 24, 14, 7, 255]))

    def test_selected_calibration_sources_and_camera_set(self) -> None:
        calibration_path = (
            ROOT / "configs" / "av2" / "54bc6dbc-ebfb-3fba-b5b3-57f88b4b79ca" / "calibration.json"
        )
        document = json.loads(calibration_path.read_text())
        self.assertEqual(document["log_id"], "54bc6dbc-ebfb-3fba-b5b3-57f88b4b79ca")
        self.assertEqual({item["sensor_name"] for item in document["cameras"]}, set(CAMERA_ORDER))
        for relative, expected in document["source"]["files"].items():
            actual = hashlib.sha256((calibration_path.parent / relative).read_bytes()).hexdigest()
            self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
