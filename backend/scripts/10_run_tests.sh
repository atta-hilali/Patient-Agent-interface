#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -d ".venv" ]]; then
  echo "Missing backend/.venv. Create it first:"
  echo "python3 -m venv .venv"
  exit 1
fi

source .venv/bin/activate
pip install -r requirements-dev.txt
PYTHONPATH=. pytest -q
