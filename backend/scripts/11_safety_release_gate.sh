#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -d ".venv" ]]; then
  echo "Missing backend/.venv. Create it first: python3 -m venv .venv"
  exit 1
fi

source .venv/bin/activate

echo "[safety-gate] Installing dependencies"
pip install -r requirements-dev.txt >/dev/null

export PYTHONPATH=.
export NEMOGUARD_ENABLED=true
export NEMOGUARD_CONTENT_ENABLED=true
export NEMOGUARD_TOPIC_ENABLED=true
export NEMOGUARD_FAIL_OPEN=false
export NEMOGUARD_STRICT_ORDER=true

echo "[safety-gate] Running crisis/false-positive preflight tests"
pytest -q tests/test_preflight.py

echo "[safety-gate] Running safety checker tests"
pytest -q tests/test_safety_checker.py

echo "[safety-gate] Running strict 200-case adversarial suite"
pytest -q tests/test_safety_checker.py::SafetyCheckerTests::test_adversarial_suite_of_200_cases

echo "[safety-gate] PASS"

