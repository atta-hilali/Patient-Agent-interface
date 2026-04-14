#!/usr/bin/env bash
set -euo pipefail

: "${NGC_API_KEY:?NGC_API_KEY is required}"
: "${LOCAL_NIM_CACHE:=$HOME/.cache/nim}"
: "${NEMOGUARD_TC_CONTAINER:=topiccontrol}"
: "${NEMOGUARD_TC_IMAGE:=nvcr.io/nim/nvidia/llama-3.1-nemoguard-8b-topic-control:1.10.1}"
: "${NEMOGUARD_TC_HOST_PORT:=8003}"
: "${NEMOGUARD_TC_CONTAINER_PORT:=8000}"
: "${NEMOGUARD_TC_MODEL_NAME:=llama-nemotron-topic-guard-v1}"
# Keep custom name aligned with served name unless explicitly overridden.
: "${NEMOGUARD_TC_CUSTOM_MODEL_NAME:=$NEMOGUARD_TC_MODEL_NAME}"
# Keep shared memory configurable for different GPU hosts.
: "${NEMOGUARD_TC_SHM_SIZE:=16GB}"
: "${NEMOGUARD_TC_GPU_DEVICE:=0}"
# Set this if auto-profile selection crashes on your platform.
: "${NEMOGUARD_TC_MODEL_PROFILE:=}"

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

echo
echo "Tail logs:"
echo "docker logs -f $NEMOGUARD_TC_CONTAINER"
echo
echo "Health probe:"
echo "curl -fsS http://127.0.0.1:${NEMOGUARD_TC_HOST_PORT}/v1/health/ready"
