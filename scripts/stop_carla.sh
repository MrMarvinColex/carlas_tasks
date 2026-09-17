#!/usr/bin/env bash
# Stop only the named project CARLA container; it never deletes images or project data.
set -euo pipefail

name="${CARLA_CONTAINER_NAME:-carla-server}"
if ! sudo docker container inspect "$name" >/dev/null 2>&1; then
  echo "No container named '$name' exists; nothing to stop."
  exit 0
fi

image="$(sudo docker container inspect --format '{{.Config.Image}}' "$name")"
if [[ "$image" != carlasim/carla:0.9.16 ]]; then
  echo "ERROR: refusing to stop '$name': it uses '$image', not carlasim/carla:0.9.16." >&2
  exit 1
fi
sudo docker stop "$name"
