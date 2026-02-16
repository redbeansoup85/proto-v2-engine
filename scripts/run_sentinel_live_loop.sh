#!/usr/bin/env bash
set -euo pipefail

MODE="${MODE:-dummy}"                              # real|dummy
EXECUTION_MODE="${EXECUTION_MODE:-dry_run}"        # dry_run|paper|live

# Default: outbox-only. Direct exec must be explicitly enabled.
LOOP_DIRECT_EXEC="${LOOP_DIRECT_EXEC:-0}"
EXECUTOR_URL="${EXECUTOR_URL:-http://127.0.0.1:8787/execute_market}"
EXECUTOR_FAIL_STREAK_MAX="${EXECUTOR_FAIL_STREAK_MAX:-3}"

SYMBOLS="${SYMBOLS:-BTCUSDT,ETHUSDT}"              # comma-separated
TFS="${TFS:-15m 1h}"                               # space-separated
INTERVAL_SEC="${INTERVAL_SEC:-60}"
CYCLES="${CYCLES:-1}"

SNAP_ROOT="/tmp/metaos_snapshots"
DERIV_ROOT="/tmp/metaos_derivatives"
DOMAIN_ROOT="/tmp/metaos_domain_events"

# executor fail streak persistence (process-external)
STATE_DIR="var/metaos/state"
FAIL_FILE="${STATE_DIR}/executor_fail_streak.txt"
mkdir -p "$STATE_DIR"

for ((c=1; c<=CYCLES; c++)); do
  TS_COMPACT="$(date -u +%Y%m%dT%H%M%SZ)"
  export TS_COMPACT

  TS_ISO="$(python - <<'PY'
import os
ts=os.environ["TS_COMPACT"]
y=ts[0:4]; m=ts[4:6]; d=ts[6:8]
hh=ts[9:11]; mm=ts[11:13]; ss=ts[13:15]
print(f"{y}-{m}-{d}T{hh}:{mm}:{ss}Z")
PY
)"

  TS="$TS_COMPACT"

  echo "MODE=$MODE"
  echo "================ Cycle $c ($TS) ================"

  # ---------------------------------------------------
  # LIVE AUTHORITY GATE (hard fail-closed)
  # ---------------------------------------------------
  if [ "$EXECUTION_MODE" = "live" ]; then

    [ "${LIVE_ENABLE:-}" = "1" ] || { echo "FATAL: LIVE_ENABLE must be 1"; exit 1; }
    [ "${HUMAN_APPROVAL:-}" = "YES" ] || { echo "FATAL: HUMAN_APPROVAL must be YES"; exit 1; }
    [ -n "${APPROVER_ID:-}" ] || { echo "FATAL: APPROVER_ID required"; exit 1; }
    [ -n "${APPROVAL_TICKET:-}" ] || { echo "FATAL: APPROVAL_TICKET required"; exit 1; }
    [ -n "${APPROVAL_TS:-}" ] || { echo "FATAL: APPROVAL_TS required"; exit 1; }

    [[ "${MAX_NOTIONAL_USD:-}" =~ ^[0-9]+$ ]] || { echo "FATAL: MAX_NOTIONAL_USD must be integer"; exit 1; }
    [[ "${MAX_ORDERS_PER_CYCLE:-}" =~ ^[0-9]+$ ]] || { echo "FATAL: MAX_ORDERS_PER_CYCLE must be integer"; exit 1; }
    [[ "${MAX_POSITIONS:-}" =~ ^[0-9]+$ ]] || { echo "FATAL: MAX_POSITIONS must be integer"; exit 1; }
    [[ "${LIVE_COOLDOWN_SEC:-}" =~ ^[0-9]+$ ]] || { echo "FATAL: LIVE_COOLDOWN_SEC must be integer"; exit 1; }
  fi

  IFS=',' read -r -a SYM_ARR <<< "$SYMBOLS"

  for S in "${SYM_ARR[@]}"; do

    DER_DIR="${DERIV_ROOT}/${S}"
    mkdir -p "$DER_DIR"
    DER="${DER_DIR}/deriv_${TS}.json"

    if [ "$MODE" = "real" ]; then
      python tools/sentinel_fetch_binance_derivatives.py \
        --symbol "$S" \
        --out "$DER" || exit 1
    else
      cat > "$DER" <<JSON
{
  "symbol": "$S",
  "ts_iso": "$TS_ISO",
  "derivatives": {
    "open_interest": 100000
  }
}
JSON
    fi

    for TF in $TFS; do
      SNAP_DIR="${SNAP_ROOT}/${S}_${TF}"
      EVT_DIR="${DOMAIN_ROOT}/${S}"
      mkdir -p "$SNAP_DIR" "$EVT_DIR"

      SNAP="${SNAP_DIR}/snapshot_${TS}.json"
      EVT="${EVT_DIR}/domain_event_${TS}_${TF}.json"

      if [ "$MODE" = "real" ]; then
        python tools/sentinel_fetch_bybit_candle.py \
          --symbol "$S" --tf "$TF" \
          --out "$SNAP" || exit 1
      else
        cat > "$SNAP" <<JSON
{
  "symbol": "$S",
  "timeframe": "$TF",
  "ts_iso": "$TS_ISO",
  "ohlc": {
    "open": 24800,
    "high": 24900,
    "low": 24750,
    "close": 24850,
    "volume": 123.45
  },
  "ts": "$TS"
}
JSON
      fi

      python tools/sentinel_emit_domain_event.py \
        --symbol "$S" --tf "$TF" \
        --snapshot-path "$SNAP" \
        --deriv-path "$DER" \
        --out "$EVT" || exit 1

      python sdk/validate_domain_event.py "$EVT" || exit 1
    done
  done

  SUMMARY_DIR="${DOMAIN_ROOT}/_summary"
  mkdir -p "$SUMMARY_DIR"
  SUMMARY_OUT="${SUMMARY_DIR}/summary_${TS}.json"

  python tools/sentinel_build_summary.py \
    --ts "$TS" \
    --symbols "$SYMBOLS" \
    --tfs "$TFS" \
    --out "$SUMMARY_OUT" || exit 1

  echo "OK: summary=$SUMMARY_OUT"

  # ---------------------------------------------------
  # EXECUTION INTENT (outbox-only)
  # ---------------------------------------------------
  python tools/sentinel_build_execution_intent.py \
    --summary-file "$SUMMARY_OUT" \
    --outbox "/tmp/orch_outbox_live/SENTINEL_EXEC" \
    --policy-file "policies/sentinel/exec_trigger_v1.yaml" \
    --policy-sha256 "c3c14d953ffae4cd1966d26d2c05d0d5c418fd7591981d0096f4e7554697018c" \
    --execution-mode "$EXECUTION_MODE" || exit 1

  INTENT_PATH="/tmp/orch_outbox_live/SENTINEL_EXEC/intent_${TS}.json"

  # ---------------------------------------------------
  # LIVE EXECUTOR CALL (HTTP) — gated + persistent fail-streak
  # ---------------------------------------------------
  if [ "${EXECUTION_MODE}" = "live" ] && [ "${LOOP_DIRECT_EXEC}" = "1" ]; then
    SHOULD_POST="$(INTENT_PATH="$INTENT_PATH" python - <<'PY'
import json, os
from pathlib import Path
doc=json.loads(Path(os.environ["INTENT_PATH"]).read_text(encoding="utf-8"))
items=((doc.get("intent") or {}).get("items")) or []
print("1" if any(bool(it.get("triggered")) for it in items) else "0")
PY
)"
    if [ "$SHOULD_POST" = "1" ]; then
      FAIL_STREAK="$(cat "$FAIL_FILE" 2>/dev/null || echo 0)"

      HTTP_CODE="$(curl -sS -o /tmp/sentinel_executor_last_response.json \
        -w "%{http_code}" \
        -X POST "$EXECUTOR_URL" \
        -H "Content-Type: application/json" \
        --data-binary @"$INTENT_PATH" || echo "000")"

      if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "409" ]; then
        echo 0 > "$FAIL_FILE"
        echo "OK: executor_post http=$HTTP_CODE intent=$INTENT_PATH"
      else
        FAIL_STREAK=$((FAIL_STREAK+1))
        echo "$FAIL_STREAK" > "$FAIL_FILE"
        echo "ERROR: executor_post_failed http=$HTTP_CODE fail_streak=$FAIL_STREAK max=$EXECUTOR_FAIL_STREAK_MAX intent=$INTENT_PATH"
        if [ "$FAIL_STREAK" -gt "$EXECUTOR_FAIL_STREAK_MAX" ]; then
          echo "FATAL: executor_fail_streak_exceeded -> exit 1"
          exit 1
        fi
      fi
    else
      echo "INFO: live mode but no triggered items; skip POST"
    fi
  else
    echo "INFO: outbox-only (EXECUTION_MODE=$EXECUTION_MODE LOOP_DIRECT_EXEC=$LOOP_DIRECT_EXEC) intent=$INTENT_PATH"
  fi

  echo "Live loop complete."

  if [ "$c" -lt "$CYCLES" ]; then
    sleep "$INTERVAL_SEC"
  fi
done
