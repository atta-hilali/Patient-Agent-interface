#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f ".env" ]]; then
  echo "Missing backend/.env file."
  echo "Copy .env.example to .env and fill real values first."
  exit 1
fi

if [[ ! -d ".venv" ]]; then
  echo "Missing backend/.venv. Create it first:"
  echo "python3 -m venv .venv"
  exit 1
fi

source .venv/bin/activate
set -a
source .env
set +a

: "${MEDGEMMA_MODE:=mvp}"
: "${MEDGEMMA_MVP_MODEL:=google/medgemma-4b-it}"
: "${MEDGEMMA_SPRINT3_MODEL:=google/medgemma-27b-it}"
: "${MEDGEMMA_MAX_TOKENS:=1024}"
: "${MEDGEMMA_PORT:=8080}"
: "${MEDGEMMA_MAX_MODEL_LEN:=4096}"
: "${MEDGEMMA_GPU_MEMORY_UTILIZATION:=0.45}"
: "${MEDGEMMA_MAX_NUM_SEQS:=8}"
: "${MEDGEMMA_MAX_NUM_BATCHED_TOKENS:=2048}"
: "${MEDGEMMA_DTYPE:=bfloat16}"
: "${MEDGEMMA_ENABLE_CHUNKED_PREFILL:=true}"
: "${MEDGEMMA_GPU_DEVICE:=0}"
: "${ALLOW_OVERSUBSCRIBE:=false}"
: "${MEDGEMMA_STARTUP_MEMORY_GUARD_PCT:=85}"

MODEL_NAME="$MEDGEMMA_MVP_MODEL"
TP_SIZE="${MEDGEMMA_TENSOR_PARALLEL_SIZE:-1}"
if [[ "$MEDGEMMA_MODE" == "sprint3" || "$MEDGEMMA_MODE" == "27b" || "$MEDGEMMA_MODE" == "production" ]]; then
  MODEL_NAME="$MEDGEMMA_SPRINT3_MODEL"
  TP_SIZE="${MEDGEMMA_TENSOR_PARALLEL_SIZE:-2}"
fi

echo "Starting MedGemma via vLLM"
echo "Model: $MODEL_NAME"
echo "Mode:  $MEDGEMMA_MODE"
echo "Port:  $MEDGEMMA_PORT"
echo "TP:    $TP_SIZE"
echo "GPU:   $MEDGEMMA_GPU_DEVICE"
echo "Len:   $MEDGEMMA_MAX_MODEL_LEN"
echo "VRAM:  $MEDGEMMA_GPU_MEMORY_UTILIZATION"
echo "Seqs:  $MEDGEMMA_MAX_NUM_SEQS"
echo "OpenAI base URL: http://127.0.0.1:${MEDGEMMA_PORT}/v1"

if command -v nvidia-smi >/dev/null 2>&1; then
  mem_line="$(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits -i "$MEDGEMMA_GPU_DEVICE" 2>/dev/null || true)"
  if [[ -n "$mem_line" ]]; then
    used_mem="$(echo "$mem_line" | awk -F',' '{gsub(/ /, "", $1); print $1}')"
    total_mem="$(echo "$mem_line" | awk -F',' '{gsub(/ /, "", $2); print $2}')"
    if [[ "$used_mem" =~ ^[0-9]+$ && "$total_mem" =~ ^[0-9]+$ && "$total_mem" -gt 0 ]]; then
      used_pct=$(( 100 * used_mem / total_mem ))
      echo "GPU memory before start: ${used_mem}MiB / ${total_mem}MiB (${used_pct}%)"
      if (( used_pct >= MEDGEMMA_STARTUP_MEMORY_GUARD_PCT )) && [[ "$ALLOW_OVERSUBSCRIBE" != "true" ]]; then
        echo "GPU is already above ${MEDGEMMA_STARTUP_MEMORY_GUARD_PCT}% memory."
        echo "Refusing to start MedGemma to avoid DGX instability."
        echo "Set ALLOW_OVERSUBSCRIBE=true to force start."
        exit 1
      fi
    fi
  fi
fi

VLLM_ARGS=(
  "$MODEL_NAME"
  --tensor-parallel-size "$TP_SIZE"
  --max-model-len "$MEDGEMMA_MAX_MODEL_LEN"
  --dtype "$MEDGEMMA_DTYPE"
  --port "$MEDGEMMA_PORT"
  --gpu-memory-utilization "$MEDGEMMA_GPU_MEMORY_UTILIZATION"
  --max-num-seqs "$MEDGEMMA_MAX_NUM_SEQS"
  --max-num-batched-tokens "$MEDGEMMA_MAX_NUM_BATCHED_TOKENS"
)

if [[ "$MEDGEMMA_ENABLE_CHUNKED_PREFILL" == "true" ]]; then
  VLLM_ARGS+=(--enable-chunked-prefill)
fi

export CUDA_VISIBLE_DEVICES="$MEDGEMMA_GPU_DEVICE"

exec vllm serve "${VLLM_ARGS[@]}" \
  "$@"
