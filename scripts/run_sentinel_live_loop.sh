#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="${PYTHON_BIN:-python3}"
fi

SYMBOL="${SYMBOL:-BTCUSDT}"
SYMBOLS="${SYMBOLS:-}"
INTERVAL_SEC="${INTERVAL_SEC:-60}"
TFS="${TFS:-15m,1h,4h}"

run_for_symbol() {
  local S="$1"
  local TS="$2"
  local SNAP="/tmp/metaos_snapshots/${S}/snapshot_${TS}.json"
  local EVT="/tmp/metaos_domain_events/${S}/domain_event_${TS}.json"

  mkdir -p "/tmp/metaos_snapshots/${S}" "/tmp/metaos_domain_events/${S}"

  "$PY" "$ROOT/tools/sentinel_score_snapshot_v0_2.py" \
    --symbol "$S" \
    --tf "$TFS" \
    --out "$SNAP"

  "$PY" "$ROOT/tools/sentinel_build_domain_event.py" \
    --snapshot-file "$SNAP" \
    --out "$EVT"

  echo "OK: symbol=${S} snapshot=$SNAP domain_event=$EVT"
}

while true; do
  TS="$(date -u +%Y%m%dT%H%M%SZ)"
  SYMBOLS_OR_SYMBOL="$SYMBOL"

  if [[ -n "$SYMBOLS" ]]; then
    SYMBOLS_OR_SYMBOL="$SYMBOLS"
    IFS=',' read -r -a RAW_SYMBOLS <<< "$SYMBOLS"
    for raw in "${RAW_SYMBOLS[@]}"; do
      S="${raw//[[:space:]]/}"
      if [[ -z "$S" ]]; then
        echo "FAIL-CLOSED: SYMBOLS contains empty symbol"
        exit 1
      fi
      run_for_symbol "$S" "$TS"
    done
  else
    run_for_symbol "$SYMBOL" "$TS"
  fi

  "$PY" "$ROOT/tools/sentinel_build_summary.py" \
    --ts "$TS" \
    --symbols "$SYMBOLS_OR_SYMBOL" \
    --out "/tmp/metaos_domain_events/_summary/summary_${TS}.json"
  sleep "$INTERVAL_SEC"
done
