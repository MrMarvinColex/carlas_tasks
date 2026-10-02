#!/usr/bin/env bash
# Start one owned local offscreen server; readiness means CARLA RPC responds.
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
image="${CARLA_IMAGE:-carlasim/carla:0.9.16@sha256:aaf1df22702780ece072069e23d03c4879b002ae028c79744b09c4c7ddbae953}"
name="${CARLA_CONTAINER_NAME:-carla-server}"
host="${CARLA_HOST:-127.0.0.1}"
port="${CARLA_PORT:-2000}"
log_dir="${CARLA_LOG_DIR:-logs}"
startup_timeout="${CARLA_STARTUP_TIMEOUT:-180}"
python_bin="${CARLA_PYTHON:-$project_root/.venv/bin/python}"
lease="${CARLA_SERVER_LEASE:-}"
attach=0
if [[ "${1:-}" == "--attach" && "$#" == 1 ]]; then attach=1
elif [[ "$#" != 0 ]]; then echo "Usage: bash scripts/run_carla.sh [--attach]" >&2; exit 2; fi
if ! [[ "$port" =~ ^[0-9]+$ ]] || (( port < 1 || port > 65535 )); then
  echo "ERROR: CARLA_PORT must be between 1 and 65535" >&2; exit 2
fi
if ! [[ "$startup_timeout" =~ ^[0-9]+$ ]] || (( startup_timeout < 1 )); then
  echo "ERROR: CARLA_STARTUP_TIMEOUT must be a positive integer" >&2; exit 2
fi
if [[ ! -x "$python_bin" ]]; then
  echo "ERROR: client Python missing; run scripts/setup.sh on the VM or set CARLA_PYTHON" >&2; exit 2
fi
docker_cmd=(docker)
if ! docker info >/dev/null 2>&1; then
  if sudo -n docker info >/dev/null 2>&1; then docker_cmd=(sudo -n docker)
  else echo "ERROR: Docker access unavailable; inspect VM permissions" >&2; exit 2; fi
fi
probe() { "$python_bin" -m carla_tasks server-status --host "$host" --port "$port" --timeout 2 --quiet; }
if "${docker_cmd[@]}" container inspect "$name" >/dev/null 2>&1; then
  existing_image="$("${docker_cmd[@]}" container inspect --format '{{.Config.Image}}' "$name")"
  if [[ "$attach" == 1 && "$existing_image" == "$image" ]] && probe; then
    echo "CARLA RPC ready at $host:$port; attached to $name"
    exit 0
  fi
  echo "ERROR: existing container '$name'; use --attach only for a healthy matching server" >&2; exit 1
fi
if [[ "$host" != 127.0.0.1 && "$host" != localhost ]]; then
  echo "ERROR: this launcher manages only a local server" >&2; exit 2
fi
if "$python_bin" -c 'import socket,sys; s=socket.socket(); s.settimeout(1); sys.exit(s.connect_ex((sys.argv[1],int(sys.argv[2]))))' "$host" "$port"; then
  echo "ERROR: port $port is occupied; inspect its owner before starting" >&2; exit 1
fi
mkdir -p "$log_dir"
if [[ -n "$lease" && -e "$lease" ]]; then
  echo "ERROR: server lease already exists; use a unique attempt path" >&2; exit 2
fi
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
log_file="$log_dir/carla-${timestamp}-$$.log"
container_id=""
ready=0
cleanup() {
  if [[ -n "$container_id" ]]; then
    "${docker_cmd[@]}" logs "$container_id" >"$log_file" 2>&1 || true
    if [[ "$ready" != 1 ]]; then
      "${docker_cmd[@]}" stop "$container_id" >/dev/null 2>&1 || true
    fi
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
container_id="$("${docker_cmd[@]}" run -d --rm \
  --name "$name" --label carla_tasks.owner=project \
  --runtime=nvidia --net=host --shm-size=2g \
  -e NVIDIA_VISIBLE_DEVICES=all -e NVIDIA_DRIVER_CAPABILITIES=all \
  "$image" bash CarlaUE4.sh -RenderOffScreen -nosound -quality-level=Low "-carla-port=$port")"
if [[ -n "$lease" ]]; then
  mkdir -p "$(dirname "$lease")"
  (set -o noclobber; printf '%s\n' "$container_id" >"$lease")
fi
deadline=$((SECONDS + startup_timeout))
while (( SECONDS < deadline )); do
  if ! "${docker_cmd[@]}" container inspect "$container_id" >/dev/null 2>&1; then break; fi
  if probe; then ready=1; break; fi
  sleep 2
done
if [[ "$ready" != 1 ]]; then
  echo "ERROR: CARLA RPC not ready; owned container will stop; logs: $log_file" >&2; exit 1
fi
echo "CARLA RPC ready at $host:$port (container $name; log $log_file)"
