import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from stage6_scene_spec import (  # noqa: E402
    Refusal,
    SceneSpecError,
    canonical_json_sha256,
    load_route_geometry,
    load_stage6_config,
    parse_response_json,
    parse_scene_spec_json,
    resolve_scene_spec,
)


class Stage6SceneSpecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_stage6_config(ROOT / "configs" / "stage6_scene_editing.json")
        cls.route = load_route_geometry(ROOT, cls.config, "route_01_straight")
        cls.fixtures = ROOT / "fixtures" / "stage6"

    def fixture(self, name: str) -> str:
        return (self.fixtures / name).read_text()

    def test_valid_scene_resolves_only_from_route_relative_fields(self) -> None:
        spec = parse_scene_spec_json(self.fixture("valid_parked_vehicle.json"))
        resolved = resolve_scene_spec(spec, self.config, self.route)
        self.assertEqual(resolved.route.route_id, "route_01_straight")
        self.assertEqual(len(resolved.edits), 1)
        edit = resolved.edits[0]
        self.assertAlmostEqual(edit.target_progress_m, 40.0)
        self.assertNotEqual((edit.x, edit.y), (0.0, 0.0))
        self.assertEqual(edit.anchor.side, "left")

    def test_composite_scene_resolves(self) -> None:
        spec = parse_scene_spec_json(self.fixture("valid_composite_scene.json"))
        resolved = resolve_scene_spec(spec, self.config, self.route)
        self.assertEqual(len(resolved.edits), 2)
        self.assertEqual({item.blueprint_id for item in resolved.edits}, {"vehicle.audi.a2"})

    def test_direct_coordinates_are_rejected(self) -> None:
        with self.assertRaises(SceneSpecError) as context:
            parse_scene_spec_json(self.fixture("invalid_direct_coordinates.json"))
        self.assertEqual(context.exception.code, "unexpected_field")

    def test_structurally_valid_spatial_conflict_is_rejected_before_carla(self) -> None:
        spec = parse_scene_spec_json(self.fixture("spatial_conflict.json"))
        with self.assertRaises(SceneSpecError) as context:
            resolve_scene_spec(spec, self.config, self.route)
        self.assertEqual(context.exception.code, "spatial_conflict")

    def test_animal_request_has_structured_refusal(self) -> None:
        response = parse_response_json(self.fixture("animal_refusal.json"))
        self.assertIsInstance(response, Refusal)
        assert isinstance(response, Refusal)
        self.assertIn("moving_animal", response.requested_capabilities)

    def test_duplicate_keys_and_nonfinite_numbers_are_rejected(self) -> None:
        duplicate = '{"version":"1.0","version":"1.0"}'
        with self.assertRaises(SceneSpecError) as duplicate_error:
            parse_response_json(duplicate)
        self.assertEqual(duplicate_error.exception.code, "duplicate_key")
        nonfinite = self.fixture("valid_parked_vehicle.json").replace("40.0", "NaN", 1)
        with self.assertRaises(SceneSpecError) as nonfinite_error:
            parse_scene_spec_json(nonfinite)
        self.assertEqual(nonfinite_error.exception.code, "invalid_json_constant")

    def test_digest_is_canonical(self) -> None:
        self.assertEqual(canonical_json_sha256({"a": 1, "b": 2}), canonical_json_sha256({"b": 2, "a": 1}))


if __name__ == "__main__":
    unittest.main()
