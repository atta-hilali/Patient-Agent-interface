#!/usr/bin/env bash
set -euo pipefail

: "${BACKEND_HOST:=127.0.0.1}"
: "${BACKEND_PORT:=8001}"

BASE_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"

echo "Checking backend at $BASE_URL"
echo

echo "GET /health"
curl -fsS "$BASE_URL/health"
echo
echo

echo "GET /cache/status"
curl -fsS "$BASE_URL/cache/status"
echo
echo

echo "GET /workflow/sources"
curl -fsS "$BASE_URL/workflow/sources"
echo
echo

echo "GET /voice/asr/probe"
curl -fsS "$BASE_URL/voice/asr/probe"
echo
echo

echo "POST /agent/chat (expected 401 without session cookie/body session_id)"
status_code="$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/agent/chat" \
  -H "Content-Type: application/json" \
  -d '{"message":"hello"}')"
echo "status=$status_code"
echo

echo "Done."
