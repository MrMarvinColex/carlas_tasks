#!/usr/bin/env bash
# Create or update the isolated client environment.  It never touches system Python.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${PYTHON_BIN:-python3}"
venv_dir="${VENV_DIR:-$project_root/.venv}"

command -v "$python_bin" >/dev/null 2>&1 || {
  echo "ERROR: Python executable not found: $python_bin" >&2
  exit 1
}

if [[ -x "$venv_dir/bin/python" ]] && ! "$venv_dir/bin/python" -m pip --version >/dev/null 2>&1; then
  # A failed `python -m venv` can leave an executable interpreter without pip.
  # Only the default, project-local environment is safe to rebuild automatically.
  if [[ "$venv_dir" != "$project_root/.venv" ]]; then
    echo "ERROR: incomplete virtual environment at $venv_dir; remove or repair it explicitly." >&2
    exit 1
  fi
  rm -rf "$venv_dir"
fi

if [[ ! -x "$venv_dir/bin/python" ]]; then
  "$python_bin" -m venv "$venv_dir"
fi

"$venv_dir/bin/python" -m pip install --disable-pip-version-check --requirement "$project_root/requirements.txt"
"$venv_dir/bin/python" - <<'PY'
import importlib.metadata
import json
import platform
import sys

print(json.dumps({
    "python": sys.version,
    "platform": platform.platform(),
    "carla": importlib.metadata.version("carla"),
}, indent=2, sort_keys=True))
PY

echo "Environment ready: $venv_dir"
