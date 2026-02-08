#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

echo "[gate] loop-gate"
python tools/gates/loop_gate.py --root tasks

echo "[gate] bootstrap-ref-gate"
python tools/gates/bootstrap_ref_gate.py

echo "[gate] lock3-observer-gate"
python tools/gates/lock3_observer_gate.py --path tests/fixtures/observer/valid_observer.jsonl

echo "OK: gates passed"
