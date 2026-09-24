#!/usr/bin/env bash
# Stop only the named project CARLA container; it never deletes images or project data.
set -euo pipefail

name="${CARLA_CONTAINER_NAME:-carla-server}"
expected_image="${CARLA_IMAGE:-carlasim/carla:0.9.16}"
if ! sudo docker container inspect "$name" >/dev/null 2>&1; then
  echo "No container named '$name' exists; nothing to stop."
  exit 0
fi

image="$(sudo docker container inspect --format '{{.Config.Image}}' "$name")"
if [[ "$image" != "$expected_image" ]]; then
  echo "ERROR: refusing to stop '$name': it uses '$image', not expected '$expected_image'." >&2
  exit 1
fi
sudo docker stop "$name"
