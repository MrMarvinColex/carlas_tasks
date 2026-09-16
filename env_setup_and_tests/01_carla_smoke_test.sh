#!/usr/bin/env bash
set -euo pipefail

IMAGE="carlasim/carla:0.9.16"
NAME="carla-smoke-$RANDOM"

cleanup() {
  sudo docker stop "$NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

port_2000_open() {
  ss -lntH 2>/dev/null | awk '{print $4}' | grep -Eq ':2000$'
}

echo "== Pulling CARLA 0.9.16 image =="
sudo docker pull "$IMAGE"

echo "== Starting CARLA offscreen =="
sudo docker run -d --rm \
  --name "$NAME" \
  --runtime=nvidia \
  --net=host \
  --shm-size=2g \
  -e NVIDIA_VISIBLE_DEVICES=all \
  -e NVIDIA_DRIVER_CAPABILITIES=all \
  "$IMAGE" \
  bash CarlaUE4.sh -RenderOffScreen -nosound -quality-level=Low

READY=0

for _ in $(seq 1 24); do
  if ! sudo docker ps --format '{{.Names}}' | grep -qx "$NAME"; then
    echo "CARLA container stopped unexpectedly."
    break
  fi

  LOGS="$(sudo docker logs "$NAME" 2>&1 || true)"

  if port_2000_open || grep -qiE 'listening for clients|carla.*server' <<<"$LOGS"; then
    READY=1
    break
  fi

  sleep 5
done

echo
echo "== CARLA logs =="
sudo docker logs "$NAME" 2>&1 | tail -n 100

echo
echo "== GPU state during test =="
nvidia-smi

if [ "$READY" -eq 1 ]; then
  echo
  echo "PASS: CARLA 0.9.16 runs offscreen and accepts client connections."
else
  echo
  echo "FAIL: CARLA did not become ready."
  exit 1
fi
