#!/usr/bin/env bash
set -euo pipefail

: "${NGC_API_KEY:?NGC_API_KEY is required}"
: "${LOCAL_NIM_CACHE:=$HOME/.cache/nim}"
: "${NEMOGUARD_TC_CONTAINER:=topiccontrol}"
: "${NEMOGUARD_TC_IMAGE:=nvcr.io/nim/nvidia/llama-3.1-nemoguard-8b-topic-control:1.10.1}"
: "${NEMOGUARD_TC_HOST_PORT:=8003}"
: "${NEMOGUARD_TC_CONTAINER_PORT:=8000}"
: "${NEMOGUARD_TC_MODEL_NAME:=llama-nemotron-topic-guard-v1}"
: "${NEMOGUARD_TC_ENABLED:=true}"
# Keep custom name aligned with served name unless explicitly overridden.
: "${NEMOGUARD_TC_CUSTOM_MODEL_NAME:=$NEMOGUARD_TC_MODEL_NAME}"
# Keep shared memory configurable for different GPU hosts.
: "${NEMOGUARD_TC_SHM_SIZE:=16GB}"
: "${NEMOGUARD_TC_GPU_DEVICE:=0}"
: "${NEMOGUARD_TC_USE_NVIDIA_RUNTIME:=auto}"
: "${ALLOW_OVERSUBSCRIBE:=false}"
# Set this if auto-profile selection crashes on your platform.
: "${NEMOGUARD_TC_MODEL_PROFILE:=4f904d571fe60ff24695b5ee2aa42da58cb460787a968f1e8a09f5a7e862728d}"

if [[ "$NEMOGUARD_TC_ENABLED" != "true" ]]; then
  echo "NemoGuard Topic Control startup skipped (NEMOGUARD_TC_ENABLED=false)."
  exit 0
fi

mkdir -p "$LOCAL_NIM_CACHE"
chmod 700 "$LOCAL_NIM_CACHE" || true

docker rm -f "$NEMOGUARD_TC_CONTAINER" >/dev/null 2>&1 || true

echo "Starting NemoGuard Topic Control"
echo "Container: $NEMOGUARD_TC_CONTAINER"
echo "Image:     $NEMOGUARD_TC_IMAGE"
echo "Port:      $NEMOGUARD_TC_HOST_PORT -> $NEMOGUARD_TC_CONTAINER_PORT"
echo "Model:     $NEMOGUARD_TC_MODEL_NAME"
echo "SHM:       $NEMOGUARD_TC_SHM_SIZE"
echo "GPU:       $NEMOGUARD_TC_GPU_DEVICE"

MODEL_PROFILE_ARG=()
if [[ -n "$NEMOGUARD_TC_MODEL_PROFILE" ]]; then
  MODEL_PROFILE_ARG=(-e "NIM_MODEL_PROFILE=$NEMOGUARD_TC_MODEL_PROFILE")
  echo "Profile:   $NEMOGUARD_TC_MODEL_PROFILE"
fi

if command -v nvidia-smi >/dev/null 2>&1; then
  mem_line="$(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits -i "$NEMOGUARD_TC_GPU_DEVICE" 2>/dev/null || true)"
  if [[ -n "$mem_line" ]]; then
    used_mem="$(echo "$mem_line" | awk -F',' '{gsub(/ /, "", $1); print $1}')"
    total_mem="$(echo "$mem_line" | awk -F',' '{gsub(/ /, "", $2); print $2}')"
    if [[ "$used_mem" =~ ^[0-9]+$ && "$total_mem" =~ ^[0-9]+$ && "$total_mem" -gt 0 ]]; then
      used_pct=$(( 100 * used_mem / total_mem ))
      echo "GPU memory before start: ${used_mem}MiB / ${total_mem}MiB (${used_pct}%)"
      if (( used_pct >= 85 )) && [[ "$ALLOW_OVERSUBSCRIBE" != "true" ]]; then
        echo "GPU is already above 85% memory. Refusing to start topic control to avoid DGX crash."
        echo "Set ALLOW_OVERSUBSCRIBE=true if you want to force start."
        exit 1
      fi
    fi
  fi
fi

USE_RUNTIME="false"
if [[ "$NEMOGUARD_TC_USE_NVIDIA_RUNTIME" == "true" ]]; then
  USE_RUNTIME="true"
elif [[ "$NEMOGUARD_TC_USE_NVIDIA_RUNTIME" == "auto" ]]; then
  if docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q '"nvidia"'; then
    USE_RUNTIME="true"
  fi
fi

if [[ "$USE_RUNTIME" == "true" ]]; then
  docker run -d \
    --name "$NEMOGUARD_TC_CONTAINER" \
    --runtime=nvidia \
    --gpus "device=$NEMOGUARD_TC_GPU_DEVICE" \
    --shm-size="$NEMOGUARD_TC_SHM_SIZE" \
    --ulimit nofile=65535:65535 \
    -u "$(id -u)" \
    -e NGC_API_KEY="$NGC_API_KEY" \
    "${MODEL_PROFILE_ARG[@]}" \
    -e NIM_SERVED_MODEL_NAME="$NEMOGUARD_TC_MODEL_NAME" \
    -e NIM_CUSTOM_MODEL_NAME="$NEMOGUARD_TC_CUSTOM_MODEL_NAME" \
    -v "$LOCAL_NIM_CACHE:/opt/nim/.cache/" \
    -p "$NEMOGUARD_TC_HOST_PORT:$NEMOGUARD_TC_CONTAINER_PORT" \
    "$NEMOGUARD_TC_IMAGE"
else
  docker run -d \
    --name "$NEMOGUARD_TC_CONTAINER" \
    --gpus "device=$NEMOGUARD_TC_GPU_DEVICE" \
    --shm-size="$NEMOGUARD_TC_SHM_SIZE" \
    --ulimit nofile=65535:65535 \
    -u "$(id -u)" \
    -e NGC_API_KEY="$NGC_API_KEY" \
    "${MODEL_PROFILE_ARG[@]}" \
    -e NIM_SERVED_MODEL_NAME="$NEMOGUARD_TC_MODEL_NAME" \
    -e NIM_CUSTOM_MODEL_NAME="$NEMOGUARD_TC_CUSTOM_MODEL_NAME" \
    -v "$LOCAL_NIM_CACHE:/opt/nim/.cache/" \
    -p "$NEMOGUARD_TC_HOST_PORT:$NEMOGUARD_TC_CONTAINER_PORT" \
    "$NEMOGUARD_TC_IMAGE"
fi

echo
echo "Tail logs:"
echo "docker logs -f $NEMOGUARD_TC_CONTAINER"
echo
echo "Health probe:"
echo "curl -fsS http://127.0.0.1:${NEMOGUARD_TC_HOST_PORT}/v1/health/ready"
