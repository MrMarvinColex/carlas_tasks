import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from stage6_api_adapter import (  # noqa: E402
    load_json_object,
    load_protocol,
    scene_matches_task,
    validate_model_response,
)
from stage6_scene_spec import load_stage6_config, parse_scene_spec_json  # noqa: E402


class Stage6ApiAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.protocol = load_protocol(ROOT / "configs" / "stage6_api_protocol.json")
        cls.scene_config = load_stage6_config(ROOT / "configs" / "stage6_scene_editing.json")
        cls.tasks = {item["task_id"]: item for item in cls.protocol["tasks"]}

    def test_protocol_caps_full_matrix_at_nine_calls(self) -> None:
        limits = self.protocol["request_limits"]
        self.assertEqual(len(self.protocol["models"]) * len(self.protocol["tasks"]), 9)
        self.assertEqual(limits["retry_count"], 0)
        self.assertEqual(limits["maximum_total_requests"], 9)

    def test_simple_valid_scene_must_match_the_requested_anchor(self) -> None:
        raw = (ROOT / "fixtures" / "stage6" / "valid_parked_vehicle.json").read_text()
        result = validate_model_response(raw, self.tasks["simple_parked_audi"], self.scene_config)
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["instruction_fulfilled"])
        wrong = json.loads(raw)
        wrong["weather_id"] = "clear_day"
        result = validate_model_response(json.dumps(wrong), self.tasks["simple_parked_audi"], self.scene_config)
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["instruction_fulfilled"])

    def test_animal_prompt_accepts_only_the_expected_structured_refusal(self) -> None:
        raw = (ROOT / "fixtures" / "stage6" / "animal_refusal.json").read_text()
        result = validate_model_response(raw, self.tasks["unsupported_moving_animal"], self.scene_config)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["result_kind"], "refusal")

    def test_match_detects_a_wrong_second_composite_anchor(self) -> None:
        scene = parse_scene_spec_json((ROOT / "fixtures" / "stage6" / "valid_composite_scene.json").read_text())
        expected = dict(self.tasks["composite_two_parked_audis"]["expected_scene"])
        expected["edits"] = [dict(item) for item in expected["edits"]]
        expected["edits"][1]["route_progress_m"] = 74.0
        self.assertFalse(scene_matches_task(scene, expected)["passed"])

    def test_saved_attempt_result_is_an_object_for_safe_resume(self) -> None:
        path = ROOT / "fixtures" / "stage6" / "animal_refusal.json"
        self.assertIsInstance(load_json_object(path), dict)


if __name__ == "__main__":
    unittest.main()
