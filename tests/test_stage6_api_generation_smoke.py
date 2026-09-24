import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from stage6_api_generation_smoke import (  # noqa: E402
    ProviderResponseError,
    extract_dashscope_response_text,
    extract_openai_response_text,
    local_validation,
)


class Stage6ApiGenerationSmokeTests(unittest.TestCase):
    def test_extract_openai_output_text(self) -> None:
        payload = {
            "status": "completed",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "{}"}]}],
        }
        self.assertEqual(extract_openai_response_text(payload), "{}")

    def test_extract_dashscope_output_text(self) -> None:
        payload = {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}
        self.assertEqual(extract_dashscope_response_text(payload), "{}")

    def test_refusal_and_invalid_scene_are_not_accepted(self) -> None:
        with self.assertRaises(ProviderResponseError):
            extract_openai_response_text({"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal"}]}]})
        self.assertEqual(local_validation("{}") ["status"], "failed")


if __name__ == "__main__":
    unittest.main()
