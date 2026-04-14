#!/usr/bin/env bash
set -euo pipefail

: "${CONTAINER_ID:=parakeet-1-1b-ctc-en-us}"
: "${LOCAL_NIM_CACHE:=$HOME/.cache/nim}"
: "${NIM_HTTP_HOST_PORT:=9001}"
: "${NIM_GRPC_HOST_PORT:=50052}"
: "${NIM_HTTP_API_PORT:=9000}"
: "${NIM_GRPC_API_PORT:=50051}"
: "${ASR_GPU_DEVICE:=0}"
: "${ASR_SHM_SIZE:=8GB}"
: "${ASR_USE_NVIDIA_RUNTIME:=auto}"

if [[ -z "${NGC_API_KEY:-}" ]]; then
  echo "NGC_API_KEY is missing. Export it first:"
  echo "export NGC_API_KEY=\"<YOUR_NGC_API_KEY>\""
  exit 1
fi

mkdir -p "$LOCAL_NIM_CACHE"

echo "Starting ASR NIM container: $CONTAINER_ID"
echo "HTTP host port: $NIM_HTTP_HOST_PORT -> container $NIM_HTTP_API_PORT"
echo "gRPC host port: $NIM_GRPC_HOST_PORT -> container $NIM_GRPC_API_PORT"
echo "GPU: $ASR_GPU_DEVICE"

USE_RUNTIME="false"
if [[ "$ASR_USE_NVIDIA_RUNTIME" == "true" ]]; then
  USE_RUNTIME="true"
elif [[ "$ASR_USE_NVIDIA_RUNTIME" == "auto" ]]; then
  if docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q '"nvidia"'; then
    USE_RUNTIME="true"
  fi
fi

if [[ "$USE_RUNTIME" == "true" ]]; then
  docker run -it --rm --name="$CONTAINER_ID" \
    --runtime=nvidia \
    --gpus "device=$ASR_GPU_DEVICE" \
    --shm-size="$ASR_SHM_SIZE" \
    --ulimit nofile=2048:2048 \
    -e NGC_API_KEY \
    -e NIM_TAGS_SELECTOR \
    -e NIM_HTTP_API_PORT="$NIM_HTTP_API_PORT" \
    -e NIM_GRPC_API_PORT="$NIM_GRPC_API_PORT" \
    -p "$NIM_HTTP_HOST_PORT:$NIM_HTTP_API_PORT" \
    -p "$NIM_GRPC_HOST_PORT:$NIM_GRPC_API_PORT" \
    -v "$LOCAL_NIM_CACHE:/opt/nim/.cache" \
    "nvcr.io/nim/nvidia/$CONTAINER_ID:latest"
else
  docker run -it --rm --name="$CONTAINER_ID" \
    --gpus "device=$ASR_GPU_DEVICE" \
    --shm-size="$ASR_SHM_SIZE" \
    --ulimit nofile=2048:2048 \
    -e NGC_API_KEY \
    -e NIM_TAGS_SELECTOR \
    -e NIM_HTTP_API_PORT="$NIM_HTTP_API_PORT" \
    -e NIM_GRPC_API_PORT="$NIM_GRPC_API_PORT" \
    -p "$NIM_HTTP_HOST_PORT:$NIM_HTTP_API_PORT" \
    -p "$NIM_GRPC_HOST_PORT:$NIM_GRPC_API_PORT" \
    -v "$LOCAL_NIM_CACHE:/opt/nim/.cache" \
    "nvcr.io/nim/nvidia/$CONTAINER_ID:latest"
fi
