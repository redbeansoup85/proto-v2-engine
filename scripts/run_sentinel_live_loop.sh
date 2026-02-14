#!/usr/bin/env bash
set -euo pipefail

SYMBOL="${SYMBOL:-BTCUSDT}"
SYMBOLS="${SYMBOLS:-}"
INTERVAL_SEC="${INTERVAL_SEC:-60}"

TS="$(date -u +%Y%m%dT%H%M%SZ)"

while true; do
  TS="$(date -u +%Y%m%dT%H%M%SZ)"

  # symbols list 결정
  if [ -n "${SYMBOLS}" ]; then
    IFS=',' read -r -a SYM_ARR <<< "${SYMBOLS}"
  else
    SYM_ARR=("${SYMBOL}")
  fi

  # 심볼별 snapshot + domain_event
  for raw in "${SYM_ARR[@]}"; do
    S="$(echo "${raw}" | xargs)"   # trim
    [ -n "${S}" ] || { echo "ERR: empty symbol in SYMBOLS"; exit 1; }

    SNAP="/tmp/metaos_snapshots/${S}/snapshot_${TS}.json"
    EVT="/tmp/metaos_domain_events/${S}/domain_event_${TS}.json"

    mkdir -p "/tmp/metaos_snapshots/${S}" "/tmp/metaos_domain_events/${S}"

    python tools/sentinel_score_snapshot_v0_2.py --symbol "${S}" --out "${SNAP}"
    python tools/sentinel_build_domain_event.py --snapshot-file "${SNAP}" --out "${EVT}"

    echo "OK: snapshot=${SNAP} domain_event=${EVT}"
  done

  # summary (항상 1개)
  SYMBOLS_OR_SYMBOL="${SYMBOLS:-$SYMBOL}"
  mkdir -p "/tmp/metaos_domain_events/_summary"
  python tools/sentinel_build_summary.py \
    --ts "${TS}" \
    --symbols "${SYMBOLS_OR_SYMBOL}" \
    --out "/tmp/metaos_domain_events/_summary/summary_${TS}.json"

  echo "OK: summary=/tmp/metaos_domain_events/_summary/summary_${TS}.json"
  python tools/sentinel_console_dashboard.py \
    --summary-file "/tmp/metaos_domain_events/_summary/summary_${TS}.json"

  sleep "${INTERVAL_SEC}"
done
