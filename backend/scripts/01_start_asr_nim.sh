#!/usr/bin/env bash
set -euo pipefail

: "${CONTAINER_ID:=parakeet-1-1b-ctc-en-us}"
: "${LOCAL_NIM_CACHE:=$HOME/.cache/nim}"
: "${NIM_HTTP_HOST_PORT:=9001}"
: "${NIM_GRPC_HOST_PORT:=50052}"
: "${NIM_HTTP_API_PORT:=9000}"
: "${NIM_GRPC_API_PORT:=50051}"

if [[ -z "${NGC_API_KEY:-}" ]]; then
  echo "NGC_API_KEY is missing. Export it first:"
  echo "export NGC_API_KEY=\"<YOUR_NGC_API_KEY>\""
  exit 1
fi

mkdir -p "$LOCAL_NIM_CACHE"

echo "Starting ASR NIM container: $CONTAINER_ID"
echo "HTTP host port: $NIM_HTTP_HOST_PORT -> container $NIM_HTTP_API_PORT"
echo "gRPC host port: $NIM_GRPC_HOST_PORT -> container $NIM_GRPC_API_PORT"

docker run -it --rm --name="$CONTAINER_ID" \
  --gpus '"device=0"' \
  --shm-size=8GB \
  --ulimit nofile=2048:2048 \
  -e NGC_API_KEY \
  -e NIM_TAGS_SELECTOR \
  -e NIM_HTTP_API_PORT="$NIM_HTTP_API_PORT" \
  -e NIM_GRPC_API_PORT="$NIM_GRPC_API_PORT" \
  -p "$NIM_HTTP_HOST_PORT:$NIM_HTTP_API_PORT" \
  -p "$NIM_GRPC_HOST_PORT:$NIM_GRPC_API_PORT" \
  -v "$LOCAL_NIM_CACHE:/opt/nim/.cache" \
  "nvcr.io/nim/nvidia/$CONTAINER_ID:latest"

