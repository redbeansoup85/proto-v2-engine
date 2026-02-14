#!/usr/bin/env bash
set -euo pipefail

MODE="${MODE:-dummy}"                         # real|dummy
SYMBOLS="${SYMBOLS:-BTCUSDT,ETHUSDT}"         # comma-separated
TFS="${TFS:-15m 1h}"                          # space-separated
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
      cat > "$DER" <<JSON
{ "symbol": "$S", "open_interest": 0.0, "ts_iso": "$(date -u +%Y-%m-%dT%H:%M:%SZ)" }
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
  "open": 24800,
  "high": 24900,
  "low": 24750,
  "close": 24850,
  "volume": 123.45,
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
