#!/usr/bin/env bash
set -euo pipefail

MODE="${MODE:-dummy}"                              # real|dummy
EXECUTION_MODE="${EXECUTION_MODE:-dry_run}"        # dry_run|paper|live
SYMBOLS="${SYMBOLS:-BTCUSDT,ETHUSDT}"              # comma-separated
TFS="${TFS:-15m 1h}"                               # space-separated
INTERVAL_SEC="${INTERVAL_SEC:-60}"
CYCLES="${CYCLES:-1}"

# paper sizing base (required when paper orders don't include qty)
PAPER_EQUITY_USDT="${PAPER_EQUITY_USDT:-10000}"

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
      # dummy: monotonic OI based on last deriv file
      # prevents NO_TRADE_OI_DROP_VETO even if old deriv files exist
      BASE_OI=100000

      # read last OI from latest deriv file for this symbol (if any)
      LAST_OI="$(S="$S" python - <<'PY'
import json, glob, os, sys
s = os.environ["S"]
d = f"/tmp/metaos_derivatives/{s}"
paths = sorted(glob.glob(os.path.join(d, "deriv_*.json")))
if not paths:
    print("")
    sys.exit(0)
p = paths[-1]
try:
    obj = json.load(open(p, "r", encoding="utf-8"))
    oi = obj.get("derivatives", {}).get("open_interest", None)
    if isinstance(oi, (int, float)):
        print(int(oi))
    else:
        print("")
except Exception:
    print("")
PY
)"

      if [[ "$LAST_OI" =~ ^[0-9]+$ ]]; then
        OI=$((LAST_OI + 500))
      else
        OI=$BASE_OI
      fi

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
        # dummy snapshot: per-symbol realistic price scale
        if [ "$S" = "BTCUSDT" ]; then
          D_OPEN=24800; D_HIGH=24900; D_LOW=24750; D_CLOSE=24850; D_VOL=123.45
        elif [ "$S" = "ETHUSDT" ]; then
          D_OPEN=1990;  D_HIGH=2010;  D_LOW=1980;  D_CLOSE=2000;  D_VOL=456.78
        else
          D_OPEN=100;   D_HIGH=101;   D_LOW=99;    D_CLOSE=100;   D_VOL=10.0
        fi

        cat > "$SNAP" <<JSON
{
  "symbol": "$S",
  "timeframe": "$TF",
  "ts_iso": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "ohlc": {
    "open": $D_OPEN,
    "high": $D_HIGH,
    "low": $D_LOW,
    "close": $D_CLOSE,
    "volume": $D_VOL
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
  #  + Paper fills + audit append + (optional) ledger
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

    # --- python selector (prefer venv) ---

    PY_BIN=".venv/bin/python"

    if [ ! -x "$PY_BIN" ]; then PY_BIN="python3"; fi

    $PY_BIN tools/sentinel_build_paper_orders.py \
      --execution-intent "$INTENT_PATH" \
      --outbox "/tmp/orch_outbox_live/SENTINEL_ORDERS" \
      --policy-file "$POLICY_FILE" \
      --policy-sha256 "$POLICY_SHA256" || exit 1

    PAPER_PATH="/tmp/orch_outbox_live/SENTINEL_ORDERS/paper_${TS}.json"
    test -f "$PAPER_PATH" || { echo "ERROR: paper intent not found for TS=$TS (expected $PAPER_PATH)"; exit 1; }

    # hard guard: paper orders must be non-empty
    ORDERS_N="$(python - <<PY
import json
p="$PAPER_PATH"
d=json.load(open(p,"r",encoding="utf-8"))
orders=(d.get("intent") or {}).get("orders") or d.get("orders") or []
print(len(orders))
PY
)"
    test "$ORDERS_N" -gt 0 || { echo "INFO: paper orders empty (no-action): $PAPER_PATH"; exit 0; }

    # Optional: append paper_orders to audit chain if tool exists
    if [ -f "tools/observer_append_paper_orders.py" ]; then
      python tools/observer_append_paper_orders.py \
        --paper-file "$PAPER_PATH" \
        --audit-jsonl "var/audit_chain/paper_orders.jsonl" || exit 1
    fi

    # ---- Paper Fill Simulator v1 (fail-closed in paper mode) ----
    test -f "tools/paper_fill_simulator.py" || { echo "ERROR: missing tools/paper_fill_simulator.py"; exit 1; }
    test -f "tools/observer_append_paper_fills.py" || { echo "ERROR: missing tools/observer_append_paper_fills.py"; exit 1; }

    mkdir -p "/tmp/orch_outbox_live/SENTINEL_FILLS"
    FILL_PATH="/tmp/orch_outbox_live/SENTINEL_FILLS/fill_${TS}.json"

    export PAPER_EQUITY_USDT="$PAPER_EQUITY_USDT"

    PYTHONPATH="$(pwd)" .venv/bin/python tools/paper_fill_simulator.py \
      --input "$PAPER_PATH" \
      --out "$FILL_PATH" || exit 1

    test -f "$FILL_PATH" || { echo "ERROR: expected fill not found: $FILL_PATH"; exit 1; }

    PYTHONPATH="$(pwd)" .venv/bin/python tools/observer_append_paper_fills.py \
      --input "$FILL_PATH" \
      --chain "var/audit_chain/paper_fills.jsonl" || exit 1

    # Optional: ledger SSOT (fail-closed if tool exists but fails)
    if [ -f "tools/ledger_paper_positions.py" ]; then
      LEDGER_PATH="/tmp/orch_outbox_live/SENTINEL_FILLS/ledger_${TS}.json"
      PYTHONPATH="$(pwd)" .venv/bin/python tools/ledger_paper_positions.py \
        --chain "var/audit_chain/paper_fills.jsonl" \
        --out "$LEDGER_PATH" || exit 1
      echo "OK: paper_ledger=$LEDGER_PATH"
    fi
    echo "OK: paper_fill=$FILL_PATH"
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
