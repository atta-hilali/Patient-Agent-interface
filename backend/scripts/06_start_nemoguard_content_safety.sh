#!/usr/bin/env bash
set -euo pipefail

: "${NGC_API_KEY:?NGC_API_KEY is required}"
: "${LOCAL_NIM_CACHE:=$HOME/.cache/nim}"
: "${NEMOGUARD_CS_CONTAINER:=contentsafety}"
: "${NEMOGUARD_CS_IMAGE:=nvcr.io/nim/nvidia/llama-3.1-nemoguard-8b-content-safety:1.10.1}"
: "${NEMOGUARD_CS_HOST_PORT:=8002}"
: "${NEMOGUARD_CS_CONTAINER_PORT:=8000}"
: "${NEMOGUARD_CS_MODEL_NAME:=llama-nemotron-safety-guard-v2}"
# Use this profile on GB10 / ARM systems when TRT profile crashes:
: "${NEMOGUARD_CS_MODEL_PROFILE:=4f904d571fe60ff24695b5ee2aa42da58cb460787a968f1e8a09f5a7e862728d}"

mkdir -p "$LOCAL_NIM_CACHE"
chmod -R 777 "$LOCAL_NIM_CACHE" || true

docker rm -f "$NEMOGUARD_CS_CONTAINER" >/dev/null 2>&1 || true

echo "Starting NemoGuard Content Safety"
echo "Container: $NEMOGUARD_CS_CONTAINER"
echo "Image:     $NEMOGUARD_CS_IMAGE"
echo "Port:      $NEMOGUARD_CS_HOST_PORT -> $NEMOGUARD_CS_CONTAINER_PORT"
echo "Profile:   $NEMOGUARD_CS_MODEL_PROFILE"

docker run -d \
  --name "$NEMOGUARD_CS_CONTAINER" \
  --gpus '"device=0"' \
  --shm-size=8GB \
  --ulimit nofile=65535:65535 \
  -e NGC_API_KEY="$NGC_API_KEY" \
  -e NIM_MODEL_PROFILE="$NEMOGUARD_CS_MODEL_PROFILE" \
  -e NIM_SERVED_MODEL_NAME="$NEMOGUARD_CS_MODEL_NAME" \
  -v "$LOCAL_NIM_CACHE:/opt/nim/.cache/" \
  -p "$NEMOGUARD_CS_HOST_PORT:$NEMOGUARD_CS_CONTAINER_PORT" \
  "$NEMOGUARD_CS_IMAGE"

echo
echo "Tail logs:"
echo "docker logs -f $NEMOGUARD_CS_CONTAINER"
echo
echo "Health probe:"
echo "curl -fsS http://127.0.0.1:${NEMOGUARD_CS_HOST_PORT}/v1/health/ready"
