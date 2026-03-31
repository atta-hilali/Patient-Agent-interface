#!/usr/bin/env bash
set -euo pipefail

: "${BACKEND_HOST:=127.0.0.1}"
: "${BACKEND_PORT:=8001}"
: "${CLOUDFLARED_BIN:=$HOME/.local/bin/cloudflared}"

if [[ ! -x "$CLOUDFLARED_BIN" ]]; then
  echo "cloudflared not found at: $CLOUDFLARED_BIN"
  echo "Install it in your home directory first."
  exit 1
fi

TARGET_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"
echo "Starting cloudflared quick tunnel for ${TARGET_URL}"
exec "$CLOUDFLARED_BIN" tunnel --url "$TARGET_URL"

