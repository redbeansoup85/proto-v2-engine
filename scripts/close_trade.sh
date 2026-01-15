#!/usr/bin/env bash
# Usage:
# close_trade <REALIZED> <MAE> <MFE> <RESULT> <REASON> "<NOTES>"

set -euo pipefail

REALIZED="${1:-}"
MAE="${2:-}"
MFE="${3:-}"
RESULT="${4:-}"
REASON="${5:-}"
NOTES="${6:-}"

if [ -z "$NOTES" ]; then
  echo 'Usage: close_trade <REALIZED> <MAE> <MFE> <RESULT> <REASON> "<NOTES>"'
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v jq >/dev/null 2>&1; then
  echo "[ERROR] jq not found. Install: brew install jq"
  exit 1
fi

# 최신 COMPLETE run_id 선택 (macOS: tail -r)
RUN_ID=$(tail -r vault/manifests/runs_index.jsonl | jq -r 'select(.status=="COMPLETE") | .run_id' | head -n 1)

echo "▶ closing run_id=$RUN_ID"

# opatch (alias 대신 실제 python 호출)
PYTHONWARNINGS="ignore::UserWarning" PYTHONPATH=. python cli/outcome_patch.py \
  --run-id "$RUN_ID" \
  --realized "$REALIZED" --unrealized 0 --ccy USDT \
  --mae "$MAE" --mfe "$MFE" \
  --slippage 0 --latency-ms 0 \
  --result "$RESULT" --reason "$REASON" \
  --notes "$NOTES"

# vscan 실행 + 출력 캡처
set +e
SCAN_OUT=$(PYTHONWARNINGS="ignore::UserWarning" PYTHONPATH=. python meta_os/validator_cli.py scan \
  --run-id "$RUN_ID" --strict-context 2>&1)
SCAN_CODE=$?
set -e

echo "$SCAN_OUT"

# HARD_FAIL 후처리
if echo "$SCAN_OUT" | grep -q "\[HARD_FAIL\]"; then
  DATE=$(date -u +%Y/%m/%d)
  EX_DIR="vault/exceptions/$DATE"

  EX_PATH=$(ls "$EX_DIR"/exception_"$RUN_ID"__*.json 2>/dev/null | head -n 1 || true)

  echo ""
  echo "🚨 HARD_FAIL detected for run_id=$RUN_ID"

  if [ -n "$EX_PATH" ]; then
    CODE=$(jq -r '.code // ""' "$EX_PATH")
    TERM=$(jq -r '.evidence.finding.term // ""' "$EX_PATH" 2>/dev/null || true)

    echo "→ exception file: $EX_PATH"
    echo "→ code: $CODE"
    if [ -n "$TERM" ] && [ "$TERM" != "null" ]; then
      echo "→ finding.term: $TERM"
    fi

    echo ""
    echo "📝 one-line memo template:"
    echo "\"HARD_FAIL:$CODE (term=${TERM}) → fix context/card wording → rerun tlog/vscan\""
  else
    echo "→ exception file not found in $EX_DIR"
    echo "📝 memo:"
    echo "\"HARD_FAIL detected but exception file not found → check vault/exceptions\""
  fi

  exit 2
fi

echo "✔ close_trade done for $RUN_ID"
