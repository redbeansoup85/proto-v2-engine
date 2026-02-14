#!/usr/bin/env bash
set -euo pipefail

SYMBOL="${SYMBOL:-BTCUSDT}"
SYMBOLS="${SYMBOLS:-}"
INTERVAL_SEC="${INTERVAL_SEC:-60}"
TFS="${TFS:-15m,1h,4h}"

TS="$(date -u +%Y%m%dT%H%M%SZ)"

while true; do
  TS="$(date -u +%Y%m%dT%H%M%SZ)"

  # symbols list 결정
  if [ -n "${SYMBOLS}" ]; then
    IFS=',' read -r -a SYM_ARR <<< "${SYMBOLS}"
  else
    SYM_ARR=("${SYMBOL}")
  fi

  IFS=',' read -r -a TF_ARR <<< "${TFS}"
  CLEAN_TFS=()
  for raw_tf in "${TF_ARR[@]}"; do
    TF="$(echo "${raw_tf}" | xargs)"   # trim
    [ -n "${TF}" ] || { echo "ERR: empty timeframe in TFS"; exit 1; }
    CLEAN_TFS+=("${TF}")
  done

  # 심볼별 x TF별 snapshot + domain_event
  for raw in "${SYM_ARR[@]}"; do
    S="$(echo "${raw}" | xargs)"   # trim
    [ -n "${S}" ] || { echo "ERR: empty symbol in SYMBOLS"; exit 1; }

    for TF in "${CLEAN_TFS[@]}"; do
      SNAP="/tmp/metaos_snapshots/${S}_${TF}/snapshot_${TS}.json"
      EVT="/tmp/metaos_domain_events/${S}_${TF}/domain_event_${TS}.json"

      mkdir -p "/tmp/metaos_snapshots/${S}_${TF}" "/tmp/metaos_domain_events/${S}_${TF}"

      # Builder enforces required TF set internally; pass full TFS list for consistency.
      python tools/sentinel_score_snapshot_v0_2.py --symbol "${S}" --tf "${TFS}" --out "${SNAP}"
      python tools/sentinel_build_domain_event.py --snapshot-file "${SNAP}" --out "${EVT}"

      echo "OK: tf=${TF} snapshot=${SNAP} domain_event=${EVT}"
    done
  done

  # summary (항상 1개)
  SYMBOLS_OR_SYMBOL="${SYMBOLS:-$SYMBOL}"
  mkdir -p "/tmp/metaos_domain_events/_summary"
  python tools/sentinel_build_summary.py \
    --ts "${TS}" \
    --symbols "${SYMBOLS_OR_SYMBOL}" \
    --tfs "${TFS}" \
    --out "/tmp/metaos_domain_events/_summary/summary_${TS}.json"

  echo "OK: summary=/tmp/metaos_domain_events/_summary/summary_${TS}.json"
  sleep "${INTERVAL_SEC}"
done
