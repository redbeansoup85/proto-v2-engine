#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/.venv/bin/activate"

export AURALIS_AUDIT_PATH="$ROOT/var/logs/audit.jsonl"
export AURALIS_GENESIS_PATH="$ROOT/var/seal/GENESIS.yaml"
export PYTHONPATH="$ROOT"

exec python -m uvicorn apps.phone_ingest.app:app --host 0.0.0.0 --port 8787
