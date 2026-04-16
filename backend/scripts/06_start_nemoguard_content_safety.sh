#!/usr/bin/env bash
set -euo pipefail

: "${NGC_API_KEY:?NGC_API_KEY is required}"
: "${LOCAL_NIM_CACHE:=$HOME/.cache/nim}"
: "${NEMOGUARD_CS_CONTAINER:=contentsafety}"
: "${NEMOGUARD_CS_IMAGE:=nvcr.io/nim/nvidia/llama-3.1-nemoguard-8b-content-safety:1.10.1}"
: "${NEMOGUARD_CS_HOST_PORT:=8002}"
: "${NEMOGUARD_CS_CONTAINER_PORT:=8000}"
: "${NEMOGUARD_CS_MODEL_NAME:=llama-nemotron-safety-guard-v2}"
: "${NEMOGUARD_CS_ENABLED:=true}"
# Use this profile on GB10 / ARM systems when TRT profile crashes:
: "${NEMOGUARD_CS_MODEL_PROFILE:=4f904d571fe60ff24695b5ee2aa42da58cb460787a968f1e8a09f5a7e862728d}"
: "${NEMOGUARD_CS_GPU_DEVICE:=0}"
: "${NEMOGUARD_CS_SHM_SIZE:=16GB}"
: "${NEMOGUARD_CS_USE_NVIDIA_RUNTIME:=auto}"
: "${ALLOW_OVERSUBSCRIBE:=false}"

if [[ "$NEMOGUARD_CS_ENABLED" != "true" ]]; then
  echo "NemoGuard Content Safety startup skipped (NEMOGUARD_CS_ENABLED=false)."
  exit 0
fi

mkdir -p "$LOCAL_NIM_CACHE"
chmod 700 "$LOCAL_NIM_CACHE" || true

docker rm -f "$NEMOGUARD_CS_CONTAINER" >/dev/null 2>&1 || true

echo "Starting NemoGuard Content Safety"
echo "Container: $NEMOGUARD_CS_CONTAINER"
echo "Image:     $NEMOGUARD_CS_IMAGE"
echo "Port:      $NEMOGUARD_CS_HOST_PORT -> $NEMOGUARD_CS_CONTAINER_PORT"
echo "Profile:   $NEMOGUARD_CS_MODEL_PROFILE"
echo "GPU:       $NEMOGUARD_CS_GPU_DEVICE"
echo "SHM:       $NEMOGUARD_CS_SHM_SIZE"

if command -v nvidia-smi >/dev/null 2>&1; then
  mem_line="$(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits -i "$NEMOGUARD_CS_GPU_DEVICE" 2>/dev/null || true)"
  if [[ -n "$mem_line" ]]; then
    used_mem="$(echo "$mem_line" | awk -F',' '{gsub(/ /, "", $1); print $1}')"
    total_mem="$(echo "$mem_line" | awk -F',' '{gsub(/ /, "", $2); print $2}')"
    if [[ "$used_mem" =~ ^[0-9]+$ && "$total_mem" =~ ^[0-9]+$ && "$total_mem" -gt 0 ]]; then
      used_pct=$(( 100 * used_mem / total_mem ))
      echo "GPU memory before start: ${used_mem}MiB / ${total_mem}MiB (${used_pct}%)"
      if (( used_pct >= 85 )) && [[ "$ALLOW_OVERSUBSCRIBE" != "true" ]]; then
        echo "GPU is already above 85% memory. Refusing to start content safety to avoid DGX crash."
        echo "Set ALLOW_OVERSUBSCRIBE=true if you want to force start."
        exit 1
      fi
    fi
  fi
fi

USE_RUNTIME="false"
if [[ "$NEMOGUARD_CS_USE_NVIDIA_RUNTIME" == "true" ]]; then
  USE_RUNTIME="true"
elif [[ "$NEMOGUARD_CS_USE_NVIDIA_RUNTIME" == "auto" ]]; then
  if docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q '"nvidia"'; then
    USE_RUNTIME="true"
  fi
fi

if [[ "$USE_RUNTIME" == "true" ]]; then
  docker run -d \
    --name "$NEMOGUARD_CS_CONTAINER" \
    --runtime=nvidia \
    --gpus "device=$NEMOGUARD_CS_GPU_DEVICE" \
    --shm-size="$NEMOGUARD_CS_SHM_SIZE" \
    --ulimit nofile=65535:65535 \
    -u "$(id -u)" \
    -e NGC_API_KEY="$NGC_API_KEY" \
    -e NIM_MODEL_PROFILE="$NEMOGUARD_CS_MODEL_PROFILE" \
    -e NIM_SERVED_MODEL_NAME="$NEMOGUARD_CS_MODEL_NAME" \
    -v "$LOCAL_NIM_CACHE:/opt/nim/.cache/" \
    -p "$NEMOGUARD_CS_HOST_PORT:$NEMOGUARD_CS_CONTAINER_PORT" \
    "$NEMOGUARD_CS_IMAGE"
else
  docker run -d \
    --name "$NEMOGUARD_CS_CONTAINER" \
    --gpus "device=$NEMOGUARD_CS_GPU_DEVICE" \
    --shm-size="$NEMOGUARD_CS_SHM_SIZE" \
    --ulimit nofile=65535:65535 \
    -u "$(id -u)" \
    -e NGC_API_KEY="$NGC_API_KEY" \
    -e NIM_MODEL_PROFILE="$NEMOGUARD_CS_MODEL_PROFILE" \
    -e NIM_SERVED_MODEL_NAME="$NEMOGUARD_CS_MODEL_NAME" \
    -v "$LOCAL_NIM_CACHE:/opt/nim/.cache/" \
    -p "$NEMOGUARD_CS_HOST_PORT:$NEMOGUARD_CS_CONTAINER_PORT" \
    "$NEMOGUARD_CS_IMAGE"
fi

echo
echo "Tail logs:"
echo "docker logs -f $NEMOGUARD_CS_CONTAINER"
echo
echo "Health probe:"
echo "curl -fsS http://127.0.0.1:${NEMOGUARD_CS_HOST_PORT}/v1/health/ready"
