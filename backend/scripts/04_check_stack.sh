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

echo "GET /voice/asr/probe"
curl -fsS "$BASE_URL/voice/asr/probe"
echo
echo

echo "Done."

