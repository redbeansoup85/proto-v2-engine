#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Prefer venv python if present; otherwise fall back to system python (CI).
if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="$(command -v python3 || command -v python)"
fi

if [ -z "${PY:-}" ]; then
  echo "ERROR: python interpreter not found"
  exit 10
fi

export PYTHONPATH="$ROOT"
export AURALIS_AUDIT_PATH="${AURALIS_AUDIT_PATH:-$ROOT/var/logs/audit_sentinel.jsonl}"
export AURALIS_GENESIS_PATH="${AURALIS_GENESIS_PATH:-$ROOT/var/seal/GENESIS.yaml}"

# Ensure dirs exist (CI-safe)
mkdir -p "$ROOT/var/logs" "$ROOT/var/local_llm" "$ROOT/var/seal"

TMP_A="/tmp/sdk_stable_A.txt"
TMP_B="/tmp/sdk_stable_B.txt"

echo "== Using python =="
"$PY" -c "import sys; print(sys.executable); print(sys.version)"

echo "== Running replay A =="
"$PY" tools/local_llm/replay_sentinel_pipeline.py | tee "$TMP_A"

echo "== Running replay B =="
"$PY" tools/local_llm/replay_sentinel_pipeline.py | tee "$TMP_B"

echo "== Strict Gate Stability Check =="
"$PY" tools/check_gate_stability.py --strict "$TMP_A" "$TMP_B"

echo "== DONE =="
