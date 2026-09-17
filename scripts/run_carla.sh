#!/usr/bin/env bash
# Start one local, offscreen CARLA server.  The matching stop script targets only this name.
set -euo pipefail

image="${CARLA_IMAGE:-carlasim/carla:0.9.16}"
name="${CARLA_CONTAINER_NAME:-carla-server}"
host="${CARLA_HOST:-127.0.0.1}"
port="${CARLA_PORT:-2000}"
log_dir="${CARLA_LOG_DIR:-logs}"
mkdir -p "$log_dir"

if ! [[ "$port" =~ ^[0-9]+$ ]]; then
  echo "ERROR: CARLA_PORT must be numeric" >&2
  exit 2
fi
if sudo docker container inspect "$name" >/dev/null 2>&1; then
  echo "ERROR: container '$name' already exists; inspect it or run scripts/stop_carla.sh." >&2
  exit 1
fi
if ss -lntH | awk '{print $4}' | grep -Eq ":${port}$"; then
  echo "ERROR: TCP port $port is already listening; do not start a second CARLA server." >&2
  exit 1
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
log_file="$log_dir/carla-${timestamp}.log"
sudo docker run -d --rm \
  --name "$name" \
  --runtime=nvidia \
  --net=host \
  --shm-size=2g \
  -e NVIDIA_VISIBLE_DEVICES=all \
  -e NVIDIA_DRIVER_CAPABILITIES=all \
  "$image" \
  bash CarlaUE4.sh -RenderOffScreen -nosound -quality-level=Low

ready=0
for _ in $(seq 1 36); do
  if ! sudo docker container inspect "$name" >/dev/null 2>&1; then
    break
  fi
  if ss -lntH | awk '{print $4}' | grep -Eq ":${port}$"; then
    ready=1
    break
  fi
  sleep 5
done
sudo docker logs "$name" >"$log_file" 2>&1 || true

if [[ "$ready" != 1 ]]; then
  echo "ERROR: CARLA did not listen on $host:$port; logs: $log_file" >&2
  exit 1
fi

echo "CARLA is ready at $host:$port (container $name; log $log_file)."
