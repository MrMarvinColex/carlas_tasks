"""Portable inputs must work in a checkout without the archived datasets."""
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from carla_tasks.inputs import (
    DEFAULT_ROUTES_DIR,
    InputValidationError,
    resolve_routes_dir,
    validate_inputs,
    validate_route_set,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from stage6_scene_spec import load_route_geometry, load_stage6_config  # noqa: E402


class PortableInputsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        shutil.copytree(ROOT / "inputs", self.root / "inputs")
        shutil.copytree(ROOT / "configs", self.root / "configs")
        self.routes = self.root / DEFAULT_ROUTES_DIR

    def read(self, path):
        return json.loads(path.read_text())

    def write(self, path, document):
        path.write_text(json.dumps(document))

    def repin(self, relative):
        """Allow schema tests to reach validation beyond the integrity check."""
        path = self.routes / relative
        provenance_path = self.routes / "provenance.json"
        provenance = self.read(provenance_path)
        payload = path.read_bytes()
        provenance["files"][relative] = {"sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
        self.write(provenance_path, provenance)

    def test_fresh_checkout_needs_no_runs_or_carla(self):
        self.assertFalse((self.root / "runs").exists())
        result = validate_inputs(self.root)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["route_sets_verified"], 1)
        self.assertEqual(result["calibrations_verified"], 1)
        config = load_stage6_config(self.root / "configs/stage6_scene_editing.json")
        geometry = load_route_geometry(self.root, config, "route_01_straight")
        self.assertAlmostEqual(geometry.length_m, 110, places=4)

    def test_missing_route_is_reported(self):
        (self.routes / "routes/route_01_straight.json").unlink()
        result = validate_inputs(self.root)
        self.assertFalse(result["valid"])
        self.assertIn("missing input file", "\n".join(result["errors"]))

    def test_same_size_tampering_is_detected(self):
        path = self.routes / "routes/route_01_straight.json"
        payload = path.read_bytes()
        path.write_bytes(payload.replace(b'"length_m": 110.0', b'"length_m": 111.0', 1))
        self.assertEqual(len(payload), path.stat().st_size)
        with self.assertRaisesRegex(InputValidationError, "SHA-256 mismatch"):
            validate_route_set(self.routes, "Town01_Opt")

    def test_provenance_cannot_read_outside_route_set(self):
        path = self.routes / "provenance.json"
        document = self.read(path)
        document["files"]["../../../configs/stage4_baseline_matrix.json"] = {"sha256": "0" * 64}
        self.write(path, document)
        with self.assertRaisesRegex(InputValidationError, "unsafe dependency path"):
            validate_route_set(self.routes, "Town01_Opt")

    def test_symlink_escape_is_rejected(self):
        outside = self.root / "outside.json"
        route = self.routes / "routes/route_01_straight.json"
        outside.write_bytes(route.read_bytes())
        route.unlink()
        route.symlink_to(outside)
        with self.assertRaisesRegex(InputValidationError, "escapes its root"):
            validate_route_set(self.routes, "Town01_Opt")

    def test_re_pinned_route_still_requires_consistent_schema(self):
        relative = "routes/route_01_straight.json"
        path = self.routes / relative
        document = self.read(path)
        document["adaptive_proposal"]["dense_indices"][1] = 999
        self.write(path, document)
        self.repin(relative)
        with self.assertRaisesRegex(InputValidationError, "adaptive indices"):
            validate_route_set(self.routes, "Town01_Opt")

    def test_wrong_map_is_rejected(self):
        path = self.root / "configs/stage4_baseline_matrix.json"
        document = self.read(path)
        document["map_name"] = "Town02"
        self.write(path, document)
        result = validate_inputs(self.root, [Path("configs/stage4_baseline_matrix.json")])
        self.assertFalse(result["valid"])
        self.assertIn("map mismatch", result["errors"][0])

    def test_calibration_sources_are_required_and_hashed(self):
        path = next((self.root / "configs/av2").glob("*/raw/intrinsics.feather"))
        path.write_bytes(b"corrupt")
        result = validate_inputs(self.root)
        self.assertFalse(result["valid"])
        self.assertIn("SHA-256 mismatch", "\n".join(result["errors"]))

    def test_sensor_timing_must_align_with_simulation_ticks(self):
        path = self.root / "configs/stage4_baseline_matrix.json"
        document = self.read(path)
        document["sensor_tick_seconds"] = 0.52
        self.write(path, document)
        result = validate_inputs(self.root, [Path("configs/stage4_baseline_matrix.json")])
        self.assertFalse(result["valid"])
        self.assertIn("integer multiple", result["errors"][0])

    def test_re_pinned_route_requires_navigation_identity(self):
        relative = "routes/route_01_straight.json"
        path = self.routes / relative
        document = self.read(path)
        del document["dense_reference"]["waypoints"][0]["road_id"]
        self.write(path, document)
        self.repin(relative)
        with self.assertRaisesRegex(InputValidationError, "navigation identity"):
            validate_route_set(self.routes, "Town01_Opt")

    def test_historical_refs_are_not_runtime_dependencies(self):
        index = self.read(self.routes / "revised_routes.json")
        self.assertTrue(index["source_run"].endswith("route-numbering-swap-b5e941"))
        self.assertFalse((self.routes / index["trim_validation_path"]).exists())
        self.assertTrue(validate_inputs(self.root)["valid"])

    def test_legacy_route_field_and_conflicting_alias(self):
        config = {"approved_routes_run": DEFAULT_ROUTES_DIR.as_posix()}
        self.assertEqual(resolve_routes_dir(config, self.root), self.routes)
        config["approved_routes"] = "another-route-set"
        with self.assertRaisesRegex(InputValidationError, "conflicting"):
            resolve_routes_dir(config, self.root)

    def test_config_path_traversal_is_rejected(self):
        result = validate_inputs(self.root, ["../private.json"])
        self.assertFalse(result["valid"])
        self.assertIn("unsafe dependency path", result["errors"][0])


if __name__ == "__main__":
    unittest.main()
