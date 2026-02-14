#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="${PYTHON_BIN:-python3}"
fi

SYMBOL="${SYMBOL:-BTCUSDT}"
INTERVAL_SEC="${INTERVAL_SEC:-60}"
TFS="${TFS:-15m,1h,4h}"

while true; do
  TS="$(date -u +%Y%m%dT%H%M%SZ)"
  SNAP="/tmp/metaos_snapshots/${SYMBOL}/snapshot_${TS}.json"
  EVT="/tmp/metaos_domain_events/${SYMBOL}/domain_event_${TS}.json"

  mkdir -p "/tmp/metaos_snapshots/${SYMBOL}" "/tmp/metaos_domain_events/${SYMBOL}"

  "$PY" "$ROOT/tools/sentinel_score_snapshot_v0_2.py" \
    --symbol "$SYMBOL" \
    --tf "$TFS" \
    --out "$SNAP"

  "$PY" "$ROOT/tools/sentinel_build_domain_event.py" \
    --snapshot-file "$SNAP" \
    --out "$EVT"

  echo "OK: snapshot=$SNAP domain_event=$EVT"
  sleep "$INTERVAL_SEC"
done
