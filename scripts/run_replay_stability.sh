#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"

if [ ! -x "$PY" ]; then
  echo "ERROR: .venv python not found at $PY"
  exit 10
fi

export PYTHONPATH="$ROOT"
export AURALIS_AUDIT_PATH="$ROOT/var/logs/audit_sentinel.jsonl"
export AURALIS_GENESIS_PATH="$ROOT/var/seal/GENESIS.yaml"

TMP_A="/tmp/sdk_stable_A.txt"
TMP_B="/tmp/sdk_stable_B.txt"

echo "== Running replay A =="
"$PY" tools/local_llm/replay_sentinel_pipeline.py | tee "$TMP_A"

echo "== Running replay B =="
"$PY" tools/local_llm/replay_sentinel_pipeline.py | tee "$TMP_B"

echo "== Strict Gate Stability Check =="
"$PY" tools/check_gate_stability.py --strict "$TMP_A" "$TMP_B"

echo "== DONE =="
