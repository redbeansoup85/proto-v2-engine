#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

echo "[gate] loop-gate"
python tools/gates/loop_gate.py --root tasks

echo "[gate] bootstrap-ref-gate"
python tools/gates/bootstrap_ref_gate.py

echo "OK: gates passed"
