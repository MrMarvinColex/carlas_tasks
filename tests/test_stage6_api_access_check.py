import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from stage6_api_access_check import load_dotenv, model_ids  # noqa: E402


class Stage6ApiAccessCheckTests(unittest.TestCase):
    def test_load_dotenv_keeps_values_private_to_the_caller(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("# local only\nOPENAI_API_KEY=example-key\nDASHSCOPE_API_KEY='other-key'\n")
            self.assertEqual(
                load_dotenv(path),
                {"OPENAI_API_KEY": "example-key", "DASHSCOPE_API_KEY": "other-key"},
            )

    def test_model_ids_accepts_only_openai_compatible_data_items(self) -> None:
        self.assertEqual(
            model_ids({"data": [{"id": "qwen-a"}, {"id": "qwen-a"}, {"name": "ignored"}, "ignored"]}),
            ["qwen-a"],
        )
        self.assertEqual(model_ids({"models": []}), [])

    def test_model_ids_accepts_model_studio_output_models(self) -> None:
        self.assertEqual(
            model_ids({"output": {"models": [{"model": "qwen3.8-flash"}, {"model": "qwen3.8-flash"}]}}),
            ["qwen3.8-flash"],
        )


if __name__ == "__main__":
    unittest.main()
