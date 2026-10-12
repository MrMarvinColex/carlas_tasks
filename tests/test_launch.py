"""Test server lifecycle contracts with fake Docker/client, never a real server."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        docker = self.root / "docker"
        docker.write_text(f"#!{sys.executable}\n" + '''import json, os, sys
from pathlib import Path
root=Path(os.environ['FAKE_ROOT']); args=sys.argv[1:]
with (root/'calls.jsonl').open('a') as f: f.write(json.dumps(args)+'\\n')
if args==['info']: sys.exit(0)
if args[:2]==['container','inspect']:
 if '--format' in args:
  print(os.environ.get('CARLA_IMAGE', 'carlasim/carla:0.9.16@sha256:aaf1df22702780ece072069e23d03c4879b002ae028c79744b09c4c7ddbae953')); sys.exit(0)
 sys.exit(0 if os.environ.get('FAKE_EXISTING')=='1' or (args[-1]=='fake-id' and (root/'started').exists()) else 1)
if args[0]=='run':
 (root/'started').write_text('1'); print('fake-id'); sys.exit(0)
if args[0]=='logs': print('server diagnostics'); sys.exit(0)
if args[0]=='stop': (root/'stopped').write_text(args[1]); sys.exit(0)
sys.exit(2)
''')
        client = self.root / "client"
        client.write_text(f"#!{sys.executable}\n" + '''import os,sys
if sys.argv[1]=='-c': sys.exit(1)
sys.exit(0 if os.environ.get('FAKE_RPC')=='1' else 1)
''')
        docker.chmod(0o755)
        client.chmod(0o755)
        self.env = {**os.environ, "PATH": str(self.root) + os.pathsep + os.environ["PATH"],
                    "FAKE_ROOT": str(self.root), "CARLA_PYTHON": str(client),
                    "CARLA_PORT": "2345", "CARLA_STARTUP_TIMEOUT": "1",
                    "CARLA_LOG_DIR": str(self.root / "logs")}
        # Mock launchers must never inherit a real server's lease path.
        self.env.pop("CARLA_SERVER_LEASE", None)

    def tearDown(self):
        self.temporary.cleanup()

    def launch(self, *args):
        return subprocess.run(["bash", str(ROOT / "scripts/run_carla.sh"), *args],
                              env=self.env, capture_output=True, text=True, timeout=10)

    def test_success_passes_port_to_server_and_does_not_stop_it(self):
        self.env["FAKE_RPC"] = "1"
        self.env["CARLA_SERVER_LEASE"] = str(self.root / "lease")
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in (self.root / "calls.jsonl").read_text().splitlines()]
        launch = next(call for call in calls if call[0] == "run")
        self.assertIn("-carla-port=2345", launch)
        self.assertFalse((self.root / "stopped").exists())
        self.assertEqual((self.root / "lease").read_text().strip(), "fake-id")
        stop = subprocess.run(["bash", str(ROOT / "scripts/stop_carla.sh"), "--lease", str(self.root / "lease")],
                              env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(stop.returncode, 0, stop.stderr)
        self.assertEqual((self.root / "stopped").read_text(), "fake-id")

    def test_rpc_failure_stops_only_created_container_and_keeps_log(self):
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.root / "stopped").read_text(), "fake-id")
        self.assertIn("server diagnostics", next((self.root / "logs").glob("*.log")).read_text())

    def test_existing_container_requires_explicit_attach(self):
        self.env.update(FAKE_EXISTING="1", FAKE_RPC="1")
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "started").exists())
        self.assertFalse((self.root / "stopped").exists())
        self.assertEqual(self.launch("--attach").returncode, 0)
