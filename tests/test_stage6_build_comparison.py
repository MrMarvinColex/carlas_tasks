import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from stage6_build_comparison import passed_route_and_camera, usage_counts  # noqa: E402


class Stage6BuildComparisonTests(unittest.TestCase):
    def test_usage_counts_normalises_both_provider_spellings(self) -> None:
        self.assertEqual(usage_counts({"input_tokens": 2, "output_tokens": 3, "total_tokens": 5}), (2, 3, 5))
        self.assertEqual(usage_counts({"prompt_tokens": 7, "completion_tokens": 11, "total_tokens": 18}), (7, 11, 18))

    def test_passing_route_and_camera_require_all_saved_checks(self) -> None:
        execution = {"status": "passed", "route_check": {"checks": {"completed": True, "no_collision": True}}, "camera_validation": {"status": "passed"}}
        self.assertEqual(passed_route_and_camera(execution), (True, True))
        execution["route_check"]["checks"]["no_collision"] = False
        self.assertEqual(passed_route_and_camera(execution), (False, True))


if __name__ == "__main__":
    unittest.main()
