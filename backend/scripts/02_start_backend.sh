#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

: "${BACKEND_HOST:=127.0.0.1}"
: "${BACKEND_PORT:=8001}"

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

echo "Starting backend on ${BACKEND_HOST}:${BACKEND_PORT}"
exec uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT"

