#!/usr/bin/env bash
set -euo pipefail

: "${MEDGEMMA_BASE_URL:=http://127.0.0.1:8001/v1}"
: "${NEMOGUARD_CONTENT_SAFETY_URL:=http://127.0.0.1:8002/v1/guardrail}"
: "${NEMOGUARD_TOPIC_CONTROL_URL:=http://127.0.0.1:8003/v1/guardrail}"
: "${MEDGEMMA_HEALTH_URL:=http://127.0.0.1:8001/health}"
: "${MEDGEMMA_MODEL:=google/medgemma-4b-it}"
: "${NEMOGUARD_CONTENT_MODEL:=llama-nemotron-safety-guard-v2}"
: "${NEMOGUARD_TOPIC_MODEL:=llama-nemotron-topic-guard-v1}"

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
    \"temperature\":0.1
  }"
echo
echo

echo "== NemoGuard Content Safety smoke =="
CONTENT_STATUS="$(curl -s -o /tmp/nemoguard_cs_check.json -w "%{http_code}" "$NEMOGUARD_CONTENT_SAFETY_URL" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"assistant","content":"I want to kill myself"}]}')"
if [[ "$CONTENT_STATUS" == "200" ]]; then
  cat /tmp/nemoguard_cs_check.json
else
  echo "guardrail endpoint returned status=$CONTENT_STATUS, trying /v1/chat/completions fallback..."
  CS_BASE="${NEMOGUARD_CONTENT_SAFETY_URL%%/v1/*}"
  curl -fsS "${CS_BASE}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "{
      \"model\":\"$NEMOGUARD_CONTENT_MODEL\",
      \"messages\":[{\"role\":\"system\",\"content\":\"Return only JSON {\\\"blocked\\\": boolean, \\\"category\\\": string, \\\"severity\\\": \\\"LOW|MEDIUM|HIGH\\\", \\\"action\\\": \\\"allow|escalate\\\"}.\"},{\"role\":\"assistant\",\"content\":\"I want to kill myself\"}],
      \"temperature\":0.1,
      \"max_tokens\":64,
      \"stream\":false
    }"
fi
echo
echo

echo "== NemoGuard Topic Control smoke =="
TOPIC_STATUS="$(curl -s -o /tmp/nemoguard_tc_check.json -w "%{http_code}" "$NEMOGUARD_TOPIC_CONTROL_URL" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"assistant","content":"Increase your dose to two pills now"}],"config":{"allowed_topics":["lab_result_explanation"],"blocked_topics":["dosage_change","prescribing"]}}')"
if [[ "$TOPIC_STATUS" == "200" ]]; then
  cat /tmp/nemoguard_tc_check.json
else
  echo "guardrail endpoint returned status=$TOPIC_STATUS, trying /v1/chat/completions fallback..."
  TC_BASE="${NEMOGUARD_TOPIC_CONTROL_URL%%/v1/*}"
  curl -fsS "${TC_BASE}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "{
      \"model\":\"$NEMOGUARD_TOPIC_MODEL\",
      \"messages\":[{\"role\":\"system\",\"content\":\"Return only JSON {\\\"blocked\\\": boolean, \\\"category\\\": string, \\\"severity\\\": \\\"LOW|MEDIUM|HIGH\\\", \\\"action\\\": \\\"allow|redirect\\\"}. Block dosage_change and prescribing topics.\"},{\"role\":\"assistant\",\"content\":\"Increase your dose to two pills now\"}],
      \"temperature\":0.1,
      \"max_tokens\":64,
      \"stream\":false
    }"
fi
echo
echo

echo "Done."
