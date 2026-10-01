#!/usr/bin/env bash
# Stop only the named project CARLA container; it never deletes images or project data.
set -euo pipefail

name="${CARLA_CONTAINER_NAME:-carla-server}"
expected_image="${CARLA_IMAGE:-carlasim/carla:0.9.16@sha256:aaf1df22702780ece072069e23d03c4879b002ae028c79744b09c4c7ddbae953}"
target="$name"
if [[ "${1:-}" == "--lease" && "$#" == 2 ]]; then
  if [[ ! -f "$2" ]]; then echo "No owned server lease exists; nothing to stop."; exit 0; fi
  target="$(cat "$2")"
  if [[ -z "$target" || "$target" == *$'\n'* || "$target" == *' '* ]]; then
    echo "ERROR: invalid owned container lease" >&2; exit 2
  fi
elif [[ "$#" != 0 ]]; then
  echo "Usage: bash scripts/stop_carla.sh [--lease FILE]" >&2; exit 2
fi
docker_cmd=(docker)
if ! docker info >/dev/null 2>&1; then
  if sudo -n docker info >/dev/null 2>&1; then docker_cmd=(sudo -n docker)
  else echo "ERROR: Docker access unavailable" >&2; exit 2; fi
fi
if ! "${docker_cmd[@]}" container inspect "$target" >/dev/null 2>&1; then
  echo "No container '$target' exists; nothing to stop."
  exit 0
fi

image="$("${docker_cmd[@]}" container inspect --format '{{.Config.Image}}' "$target")"
if [[ "$image" != "$expected_image" ]]; then
  echo "ERROR: refusing to stop '$target': it uses '$image', not expected '$expected_image'." >&2
  exit 1
fi
"${docker_cmd[@]}" stop "$target"
