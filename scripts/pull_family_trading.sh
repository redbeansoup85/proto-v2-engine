#!/usr/bin/env bash
set -euo pipefail

SRC="${HOME}/Desktop/family-trading/exports/meta_os_safe/trading_outcomes.jsonl"
DST_DIR="vault/inbox/family_trading"
DST="${DST_DIR}/trading_outcomes.jsonl"

mkdir -p "${DST_DIR}"

if [ ! -f "${SRC}" ]; then
  echo "missing_source=${SRC}"
  exit 1
fi

cp "${SRC}" "${DST}"
echo "copied_to=${DST}"

python trading_os/ingest/summarize_family_trading.py
