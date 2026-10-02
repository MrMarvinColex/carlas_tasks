import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from carla_tasks.experiments import Cell, file_sha256, resolve_experiment


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n")


def fixture(root):
    (root / "recorder.py").write_text("from helper import record\n")
    (root / "helper.py").write_text("def record(): return 1\n")
    routes = root / "inputs/routes/v1"
    write_json(routes / "revised_routes.json", {"map_name": "Town01_Opt", "dense_step_m": 2,
                                               "routes": [{"route_id": "route1", "path": "routes/route1.json"}]})
    write_json(routes / "routes/route1.json", {"map_name": "Town01_Opt", "source_run": "/old/vm/runs/r1",
                                             "waypoints": [{"x": 1, "y": 2}]})
    calibration = root / "calibration.json"
    (root / "raw.feather").write_bytes(b"raw calibration")
    write_json(calibration, {"cameras": [{"name": "front", "x": 1}], "source": {"files": {"raw.feather": file_sha256(root / "raw.feather")}}})
    config = {"experiment_id": "example-v1", "map_name": "Town01_Opt", "approved_routes_run": "inputs/routes/v1",
              "route_ids": ["route1"], "repeats_per_route_weather": 1, "execution_order_seed": 7,
              "fixed_delta_seconds": 0.05, "sensor_tick_seconds": 0.5, "mount_z_offset_m": 0.5,
              "weather_profiles": {"clear": {"description": "weather", "parameters": {"wetness": 0}}}}
    write_json(root / "config.json", config)
    return config


def fixture_plan(root, **kwargs):
    return resolve_experiment(Path("config.json"), root=root, calibration_path=Path("calibration.json"), implementation_files=("recorder.py",), **kwargs)


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.config = fixture(self.root)

    def test_clean_mac_plan_needs_no_runs_or_carla(self):
        plan = fixture_plan(self.root)
        self.assertEqual(plan.cells, (Cell("route1", "clear", 1),))
        self.assertFalse((self.root / "runs").exists())
        self.assertIn("helper.py", plan.resolved_manifest["implementation_sha256"])

    def test_more_repeats_do_not_invalidate_prior_measurement(self):
        original = fixture_plan(self.root)
        self.config.update(repeats_per_route_weather=3, description="new explanation", execution_order_seed=123,
                           disk_budget={"minimum_free_gib_before_run": 10})
        write_json(self.root / "config.json", self.config)
        revised = fixture_plan(self.root)
        self.assertEqual(original.config_fingerprint, revised.config_fingerprint)
        self.assertEqual({cell.repeat_index for cell in revised.cells}, {1, 2, 3})

    def test_matrix_expansion_preserves_existing_measurement_only(self):
        original = fixture_plan(self.root)
        cell = original.cells[0]
        self.config["weather_profiles"]["rain"] = {"parameters": {"wetness": 90}}
        write_json(self.root / "config.json", self.config)
        revised = fixture_plan(self.root)
        self.assertNotEqual(original.config_fingerprint, revised.config_fingerprint)
        self.assertEqual(original.identity(cell)["measurement_fingerprint"], revised.identity(cell)["measurement_fingerprint"])
        self.config["weather_profiles"]["clear"]["parameters"]["wetness"] = 1
        write_json(self.root / "config.json", self.config)
        changed = fixture_plan(self.root)
        self.assertNotEqual(original.identity(cell)["measurement_fingerprint"], changed.identity(cell)["measurement_fingerprint"])

    def test_cameras_geometry_map_runtime_and_code_change_identity(self):
        original = fixture_plan(self.root).config_fingerprint
        self.config["mount_z_offset_m"] = 0.7
        write_json(self.root / "config.json", self.config)
        self.assertNotEqual(original, fixture_plan(self.root).config_fingerprint)
        self.config["mount_z_offset_m"] = 0.5
        write_json(self.root / "config.json", self.config)
        self.assertNotEqual(original, fixture_plan(self.root, runtime_options={"writer_workers": 9}).config_fingerprint)
        (self.root / "helper.py").write_text("def record(): return 2\n")
        self.assertNotEqual(original, fixture_plan(self.root).config_fingerprint)
        (self.root / "helper.py").write_text("def record(): return 1\n")
        route = self.root / "inputs/routes/v1/routes/route1.json"
        write_json(route, {"map_name": "Town01_Opt", "waypoints": [{"x": 3, "y": 2}]})
        self.assertNotEqual(original, fixture_plan(self.root).config_fingerprint)

    def test_calibration_change_and_source_corruption(self):
        original = fixture_plan(self.root).config_fingerprint
        calibration_path = self.root / "calibration.json"
        calibration = json.loads(calibration_path.read_text())
        calibration["cameras"][0]["x"] = 2
        write_json(calibration_path, calibration)
        self.assertNotEqual(original, fixture_plan(self.root).config_fingerprint)
        (self.root / "raw.feather").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "calibration source hash mismatch"):
            fixture_plan(self.root)

    def test_historical_path_and_docs_do_not_change_geometry_identity(self):
        original = fixture_plan(self.root).config_fingerprint
        route_path = self.root / "inputs/routes/v1/routes/route1.json"
        route = json.loads(route_path.read_text())
        route["source_run"] = "/another/machine/runs/r1"
        write_json(route_path, route)
        (self.root / "STATUS.md").write_text("unrelated status update")
        self.assertEqual(original, fixture_plan(self.root).config_fingerprint)

    def test_route_alias_preserves_identity_but_conflicts_are_rejected(self):
        original = fixture_plan(self.root).config_fingerprint
        self.config["approved_routes"] = self.config.pop("approved_routes_run")
        write_json(self.root / "config.json", self.config)
        self.assertEqual(original, fixture_plan(self.root).config_fingerprint)
        self.config["approved_routes_run"] = "inputs/routes/other"
        write_json(self.root / "config.json", self.config)
        with self.assertRaisesRegex(ValueError, "conflict"):
            fixture_plan(self.root)

    def test_changed_image_changes_identity(self):
        with patch.dict(os.environ, {"CARLA_IMAGE": "carla@sha256:" + "a" * 64}):
            original = fixture_plan(self.root).config_fingerprint
        with patch.dict(os.environ, {"CARLA_IMAGE": "carla@sha256:" + "b" * 64}):
            self.assertNotEqual(original, fixture_plan(self.root).config_fingerprint)

    def test_mutable_image_tag_cannot_claim_reproducible_identity(self):
        with patch.dict(os.environ, {"CARLA_IMAGE": "carla:latest"}):
            with self.assertRaisesRegex(ValueError, "immutable"):
                fixture_plan(self.root)

    def test_invalid_repeat_map_and_secret_rejected(self):
        for repeats in (0, True, "2"):
            self.config["repeats_per_route_weather"] = repeats
            write_json(self.root / "config.json", self.config)
            with self.assertRaisesRegex(ValueError, "positive integer"):
                fixture_plan(self.root)
        self.config["repeats_per_route_weather"] = 1
        self.config["map_name"] = "Town02"
        write_json(self.root / "config.json", self.config)
        with self.assertRaisesRegex(ValueError, "map differs"):
            fixture_plan(self.root)
        self.config["map_name"] = "Town01_Opt"
        self.config["api_key"] = "do-not-store"
        write_json(self.root / "config.json", self.config)
        with self.assertRaisesRegex(ValueError, "credentials"):
            fixture_plan(self.root)


if __name__ == "__main__":
    unittest.main()
