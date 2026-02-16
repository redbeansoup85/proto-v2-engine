#!/usr/bin/env bash
set -euo pipefail

echo "[gate] drift (CI-equivalent)"
python tools/gates/gate_template_drift_gate.py \
  --require-template-tag \
  --workflows-root .github/workflows \
  --templates-root gatekit/templates \
  --max-tag-lines 5

echo "[gate] required checks contract (ruleset-aware)"
python tools/gates/required_checks_contract_gate.py --ruleset-name "protect-main"

echo "[gate] submodule hygiene"
python tools/gates/submodule_hygiene_gate.py --root .

echo "[ok] all CI-equivalent gates passed"
