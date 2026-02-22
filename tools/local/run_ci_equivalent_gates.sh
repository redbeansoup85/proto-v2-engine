#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN=".venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  else
    echo "[gate] error: python interpreter not found (.venv/bin/python, python3, python)"
    exit 127
  fi
fi

echo "[gate] drift (CI-equivalent)"
"$PYTHON_BIN" tools/gates/gate_template_drift_gate.py \
  --require-template-tag \
  --workflows-root .github/workflows \
  --templates-root gatekit/templates \
  --max-tag-lines 5

echo "[gate] required checks contract (ruleset-aware)"
"$PYTHON_BIN" tools/gates/required_checks_contract_gate.py --ruleset-name "protect-main"

echo "[gate] submodule hygiene"
"$PYTHON_BIN" tools/gates/submodule_hygiene_gate.py --root .

echo "[ok] all CI-equivalent gates passed"
