#!/usr/bin/env bash
set -euo pipefail

: "${MEDGEMMA_BASE_URL:=http://127.0.0.1:8001/v1}"
: "${NEMOGUARD_CONTENT_SAFETY_URL:=http://127.0.0.1:8002/v1/guardrail}"
: "${NEMOGUARD_TOPIC_CONTROL_URL:=http://127.0.0.1:8003/v1/guardrail}"
: "${MEDGEMMA_HEALTH_URL:=http://127.0.0.1:8001/health}"
: "${MEDGEMMA_MODEL:=google/medgemma-4b-it}"

echo "== MedGemma health =="
curl -fsS "$MEDGEMMA_HEALTH_URL"
echo
echo

echo "== MedGemma models =="
curl -fsS "${MEDGEMMA_BASE_URL%/}/models"
echo
echo

echo "== MedGemma chat smoke =="
curl -fsS "${MEDGEMMA_BASE_URL%/}/chat/completions" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\":\"$MEDGEMMA_MODEL\",
    \"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: OK\"}],
    \"max_tokens\":8,
    \"temperature\":0
  }"
echo
echo

echo "== NemoGuard Content Safety smoke =="
curl -fsS "$NEMOGUARD_CONTENT_SAFETY_URL" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"assistant","content":"I want to kill myself"}]}'
echo
echo

echo "== NemoGuard Topic Control smoke =="
curl -fsS "$NEMOGUARD_TOPIC_CONTROL_URL" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"assistant","content":"Increase your dose to two pills now"}],"config":{"allowed_topics":["lab_result_explanation"],"blocked_topics":["dosage_change","prescribing"]}}'
echo
echo

echo "Done."
