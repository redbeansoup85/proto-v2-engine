#!/usr/bin/env bash
set -euo pipefail

TMP_DIR="$(mktemp -d)"
CHAIN="$TMP_DIR/chain.jsonl"
SNAPS="$TMP_DIR/snaps"
OUTS="$TMP_DIR/outs"

mkdir -p "$SNAPS" "$OUTS"

# 2 events into temp chain (mock backend)
echo "BTCUSDT 롱" \
| python tools/local/llm_generate_intent.py --backend mock \
| python tools/gates/sentinel_trade_intent_schema_gate.py \
| python tools/sentinel/consume_trade_intent.py --audit-path "$CHAIN" --snapshot-dir "$SNAPS" >/dev/null

echo "SOLUSDT 숏" \
| python tools/local/llm_generate_intent.py --backend mock \
| python tools/gates/sentinel_trade_intent_schema_gate.py \
| python tools/sentinel/consume_trade_intent.py --audit-path "$CHAIN" --snapshot-dir "$SNAPS" >/dev/null

# verify chain
python tools/audits/verify_judgment_event_chain.py --path "$CHAIN"

# record one outcome (writes to repo default dir). We want temp outcome dir, so write manually.
JID="$(tail -n 1 "$CHAIN" | python -c 'import sys,json; print(json.loads(sys.stdin.read())["judgment_id"])')"
cat > "$OUTS/${JID}.json" <<JSON
{"schema":"outcome_record.v1","judgment_id":"$JID","ts_recorded_utc":"n/a","label":"WIN","pnl_r":"1.0","pnl_pct":"n/a","mae_pct":"n/a","mfe_pct":"n/a","exit_ts_utc":"n/a","notes":"ci smoke"}
JSON

# replay (uses temp chain/outcome dir)
python tools/replay/replay_judgments.py --chain-path "$CHAIN" --outcome-dir "$OUTS" >/dev/null

echo "OK sentinel smoke"
