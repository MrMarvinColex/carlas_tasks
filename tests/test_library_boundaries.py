import ast
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LibraryBoundaryTests(unittest.TestCase):
    def test_library_never_imports_stage_entrypoints(self):
        violations = []
        for path in sorted((ROOT / "carla_tasks").glob("*.py")):
            for node in ast.walk(ast.parse(path.read_text())):
                names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                for name in names:
                    if name == "scripts" or name.startswith(("scripts.", "stage2_", "stage3_", "stage4_", "stage6_", "stage7_")):
                        violations.append(f"{path.name}:{node.lineno}: {name}")
        self.assertEqual(violations, [])

    def test_core_loads_without_simulator_numerical_or_image_dependencies(self):
        code = '''import builtins
original = builtins.__import__
def offline(name, *args, **kwargs):
    if name.split('.')[0] in {'carla', 'numpy', 'PIL', 'requests'}:
        raise RuntimeError('offline core imported optional dependency: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = offline
from carla_tasks import rigs, capture, recording, capture_io
'''
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
