#!/usr/bin/env bash
set -euo pipefail

MODE="${MODE:-dummy}"                              # real|dummy
EXECUTION_MODE="${EXECUTION_MODE:-dry_run}"        # dry_run|paper|live
SYMBOLS="${SYMBOLS:-BTCUSDT,ETHUSDT}"              # comma-separated
TFS="${TFS:-15m 1h}"                               # space-separated
INTERVAL_SEC="${INTERVAL_SEC:-60}"
CYCLES="${CYCLES:-1}"

SNAP_ROOT="/tmp/metaos_snapshots"
DERIV_ROOT="/tmp/metaos_derivatives"
DOMAIN_ROOT="/tmp/metaos_domain_events"

for ((c=1; c<=CYCLES; c++)); do
  TS="$(date -u +%Y%m%dT%H%M%SZ)"
  echo "MODE=$MODE"
  echo "================ Cycle $c ($TS) ================"

  IFS=',' read -r -a SYM_ARR <<< "$SYMBOLS"

  for S in "${SYM_ARR[@]}"; do
    # -----------------------------
    # Derivatives (symbol-level, once per cycle) ✅ no TF overwrite
    # -----------------------------
    DER_DIR="${DERIV_ROOT}/${S}"
    mkdir -p "$DER_DIR"
    DER="${DER_DIR}/deriv_${TS}.json"

    if [ "$MODE" = "real" ]; then
      python tools/sentinel_fetch_binance_derivatives.py \
        --symbol "$S" \
        --out "$DER" || exit 1
    else
      # minimal dummy (only if you ever run MODE=dummy)
      # deterministic-ish OI drift so 15m OI-delta buckets get exercised
      BASE_OI=100000
      # use TS seconds (SS) to force meaningful OI delta per cycle
      SEC="${TS: -3:2}"
      STEP=$((10#$SEC))
      OI=$((BASE_OI + STEP * 500))
      cat > "$DER" <<JSON
{
  "symbol": "$S",
  "ts_iso": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "derivatives": {
    "open_interest": $OI
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

      # -----------------------------
      # Snapshot
      # -----------------------------
      if [ "$MODE" = "real" ]; then
        python tools/sentinel_fetch_bybit_candle.py \
          --symbol "$S" --tf "$TF" \
          --out "$SNAP" || exit 1
      else
        cat > "$SNAP" <<JSON
{
  "symbol": "$S",
  "timeframe": "$TF",
  "ts_iso": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
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

      # -----------------------------
      # Emit domain_event (uses snapshot + derivatives)
      # -----------------------------
      python tools/sentinel_emit_domain_event.py \
        --symbol "$S" --tf "$TF" \
        --snapshot-path "$SNAP" \
        --deriv-path "$DER" \
        --out "$EVT" || exit 1

      python sdk/validate_domain_event.py "$EVT" || exit 1
    done
  done

  # -----------------------------
  # Summary
  # -----------------------------
  SUMMARY_DIR="${DOMAIN_ROOT}/_summary"
  mkdir -p "$SUMMARY_DIR"
  SUMMARY_OUT="${SUMMARY_DIR}/summary_${TS}.json"

  python tools/sentinel_build_summary.py \
    --ts "$TS" \
    --symbols "$SYMBOLS" \
    --tfs "$TFS" \
    --out "$SUMMARY_OUT" || exit 1
  echo "OK: summary=$SUMMARY_OUT"

  # -----------------------------
  # Execution Trigger v1 (EXECUTION_MODE)
  # -----------------------------
  python tools/sentinel_build_execution_intent.py \
    --summary-file "$SUMMARY_OUT" \
    --outbox "/tmp/orch_outbox_live/SENTINEL_EXEC" \
    --policy-file "policies/sentinel/exec_trigger_v1.yaml" \
    --policy-sha256 "c3c14d953ffae4cd1966d26d2c05d0d5c418fd7591981d0096f4e7554697018c" \
    --execution-mode "$EXECUTION_MODE" || exit 1

  # -----------------------------
  # Observer Hub append (execution_intent)
  # -----------------------------
  INTENT_PATH="/tmp/orch_outbox_live/SENTINEL_EXEC/intent_${TS}.json"
  if [ -f "$INTENT_PATH" ]; then
    python tools/observer_append_execution_intent.py \
      --intent-file "$INTENT_PATH" \
      --audit-jsonl "var/audit_chain/execution_intent.jsonl" || exit 1
  else
    # fallback to latest if TS-matched not found
    LAST_INTENT="$(ls -1t /tmp/orch_outbox_live/SENTINEL_EXEC/intent_*.json 2>/dev/null | head -n 1 || true)"
    test -n "$LAST_INTENT" || { echo "ERROR: no execution_intent produced"; exit 1; }
    python tools/observer_append_execution_intent.py \
      --intent-file "$LAST_INTENT" \
      --audit-jsonl "var/audit_chain/execution_intent.jsonl" || exit 1
    INTENT_PATH="$LAST_INTENT"
  fi

  # -----------------------------
  # Paper orders (execution_mode=paper only)
  # -----------------------------
  if [ "${EXECUTION_MODE:-}" = "paper" ]; then
    POLICY_FILE="policies/sentinel/paper_orders_v1.yaml"
    test -f "$POLICY_FILE" || { echo "ERROR: missing policy file: $POLICY_FILE"; exit 1; }

    POLICY_SHA256="$(python - <<'PY'
import hashlib, pathlib
p = pathlib.Path("policies/sentinel/paper_orders_v1.yaml")
print(hashlib.sha256(p.read_bytes()).hexdigest())
PY
)"
    test -n "$POLICY_SHA256" || { echo "ERROR: failed to compute policy sha256"; exit 1; }

    test -f "$INTENT_PATH" || { echo "ERROR: missing execution intent for paper orders: $INTENT_PATH"; exit 1; }

    python tools/sentinel_build_paper_orders.py \
      --execution-intent "$INTENT_PATH" \
      --outbox "/tmp/orch_outbox_live/SENTINEL_ORDERS" \
      --policy-file "$POLICY_FILE" \
      --policy-sha256 "$POLICY_SHA256" || exit 1

    PAPER_PATH="/tmp/orch_outbox_live/SENTINEL_ORDERS/paper_${TS}.json"
    if [ -f "$PAPER_PATH" ]; then
      # Optional: append to audit chain if tool exists
      if [ -f "tools/observer_append_paper_orders.py" ]; then
        python tools/observer_append_paper_orders.py \
          --paper-file "$PAPER_PATH" \
          --audit-jsonl "var/audit_chain/paper_orders.jsonl" || exit 1
      fi
    else
      echo "WARN: paper intent not found for TS=$TS (expected $PAPER_PATH)"
      # still fail-closed? choose behavior:
      # If you want strict fail-closed for paper mode, uncomment next line:
      # exit 1
    fi
  fi

  # -----------------------------
  # Console dashboard
  # -----------------------------
  if [ -f "tools/sentinel_console_dashboard.py" ]; then
    python tools/sentinel_console_dashboard.py --summary-file "$SUMMARY_OUT" || exit 1
  fi

  # sleep unless last cycle
  if [ "$c" -lt "$CYCLES" ]; then
    sleep "$INTERVAL_SEC"
  fi
done

echo "Live loop complete."
