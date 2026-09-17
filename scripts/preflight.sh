#!/usr/bin/env bash
# Report the VM prerequisites needed before starting a CARLA stage.
# It diagnoses rather than installs or changes system state.
set -u
set -o pipefail

section() { printf '\n========== %s ==========\n' "$1"; }

section "System"
date -Is
grep '^PRETTY_NAME=' /etc/os-release 2>/dev/null || true
uname -r
printf '\nMemory:\n'
free -h 2>/dev/null || true
printf '\nDisk:\n'
df -h . / 2>/dev/null || true

section "NVIDIA GPU"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap \
    --format=csv,noheader
  printf '\nGPU state:\n'
  nvidia-smi
else
  echo "FAIL: nvidia-smi not found"
fi

section "NVIDIA runtime"
lsmod | grep '^nvidia' || true
if command -v nvidia-container-cli >/dev/null 2>&1; then
  nvidia-container-cli --version
else
  echo "WARN: nvidia-container-cli not found"
fi

section "Docker"
if command -v docker >/dev/null 2>&1; then
  docker --version
  if docker info >/dev/null 2>&1; then
    echo "PASS: Docker daemon is available for this user"
  elif sudo -n docker info >/dev/null 2>&1; then
    echo "PASS: Docker works with passwordless sudo"
  else
    echo "FAIL: Docker exists, but its daemon is unavailable to this user"
  fi
else
  echo "FAIL: Docker not found"
fi

section "Vulkan"
if command -v vulkaninfo >/dev/null 2>&1; then
  vulkaninfo --summary 2>&1 | sed -n '1,80p'
else
  echo "WARN: vulkaninfo is not installed — this is not a failure yet"
fi

section "User"
id
printf '\n========== End ==========\n'
