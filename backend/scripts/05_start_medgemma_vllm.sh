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
echo "OpenAI base URL: http://127.0.0.1:${MEDGEMMA_PORT}/v1"

exec vllm serve "$MODEL_NAME" \
  --tensor-parallel-size "$TP_SIZE" \
  --max-model-len 8192 \
  --enable-chunked-prefill \
  --dtype bfloat16 \
  --port "$MEDGEMMA_PORT"
