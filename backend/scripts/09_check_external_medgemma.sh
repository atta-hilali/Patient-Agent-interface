#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-${MEDGEMMA_BASE_URL:-http://127.0.0.1:8080/v1}}"
MODEL_NAME="${MEDGEMMA_MVP_MODEL:-google/medgemma-4b-it}"
HEALTH_URL="${MEDGEMMA_HEALTH_URL:-${BASE_URL%/v1}/health}"

echo "Checking external MedGemma compatibility"
echo "BASE_URL:   ${BASE_URL}"
echo "HEALTH_URL: ${HEALTH_URL}"
echo "MODEL:      ${MODEL_NAME}"
echo

echo "1) Health"
curl -fsS "${HEALTH_URL}"
echo
echo

echo "2) Models"
MODELS_JSON="$(curl -sS "${BASE_URL%/}/models")"
echo "${MODELS_JSON}"
echo
echo

DISCOVERED_MODEL="$(echo "${MODELS_JSON}" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p' | head -n1 || true)"
if [[ -n "${DISCOVERED_MODEL}" && "${MODEL_NAME}" != "${DISCOVERED_MODEL}" ]]; then
  echo "Using discovered model id for checks: ${DISCOVERED_MODEL} (configured: ${MODEL_NAME})"
  MODEL_NAME="${DISCOVERED_MODEL}"
  echo
fi

echo "3) Chat completions (non-stream)"
CHAT_JSON="$(curl -sS "${BASE_URL%/}/chat/completions" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\":\"${MODEL_NAME}\",
    \"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: OK\"}],
    \"max_tokens\":16,
    \"temperature\":0.1,
    \"stream\":false
  }")"
echo "${CHAT_JSON}"
echo
echo

echo "4) JSON-shape capability (response_text + citations)"
JSON_SHAPE="$(curl -sS "${BASE_URL%/}/chat/completions" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\":\"${MODEL_NAME}\",
    \"messages\":[
      {\"role\":\"system\",\"content\":\"Return valid JSON only with keys response_text and citations.\"},
      {\"role\":\"user\",\"content\":\"Say hello to the patient.\"}
    ],
    \"max_tokens\":128,
    \"temperature\":0.1,
    \"stream\":false,
    \"response_format\":{\"type\":\"json_object\"}
  }")"
echo "${JSON_SHAPE}"
echo
echo

echo "5) Stream capability"
echo "(expecting lines prefixed by 'data:' and ending with [DONE])"
timeout 20s curl -NsS "${BASE_URL%/}/chat/completions" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\":\"${MODEL_NAME}\",
    \"messages\":[{\"role\":\"user\",\"content\":\"Give 1 short sentence.\"}],
    \"max_tokens\":32,
    \"temperature\":0.1,
    \"stream\":true
  }" || true
echo
echo

echo "Done."
