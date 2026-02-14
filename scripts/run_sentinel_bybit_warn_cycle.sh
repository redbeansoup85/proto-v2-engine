#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
export PYTHONPATH="$ROOT"

SYMBOL="${1:-BTCUSDT}"
POLICY="${POLICY:-$ROOT/policies/sentinel/gate_v1.yaml}"

# 1) bybit -> norm
NORM="/tmp/norm_bybit_${SYMBOL}.json"
$PY "$ROOT/tools/bybit_fetch_norm.py" --symbol "$SYMBOL" --interval 15 --limit 200 --out "$NORM"

# 2) gate
GATE="/tmp/gate_${SYMBOL}.json"
$PY "$ROOT/sdk/gate_cli.py" --input "$NORM" --policy "$POLICY" --out "$GATE"
echo "OK: gate -> $GATE"

# 3) audit append gate decision (seal)
export AURALIS_AUDIT_PATH="${AURALIS_AUDIT_PATH:-/tmp/audit_sentinel_social.jsonl}"
rm -f "$AURALIS_AUDIT_PATH"

$PY "$ROOT/tools/audit_append_gate_chain.py" --gate "$GATE" --event-id "SOCIAL:GATE_DECISION:${SYMBOL}:1" >/dev/null
$PY "$ROOT/tools/audit/verify_chain.py" --schema "$ROOT/sdk/schemas/audit_event.v1.json" --chain "$AURALIS_AUDIT_PATH"

# 4) orch pipeline (LOCK6~8과 동일 구조를 "실제 파일"로 1회 구동)
#    - 여기선 CI determinism 스위치 끄고 실제 ts로 운영 가능
unset METAOS_CI_DETERMINISTIC_PLAN METAOS_CI_DETERMINISTIC_CONSUMER METAOS_CI_DETERMINISTIC_ORCH_PAYLOAD METAOS_CI_DETERMINISTIC_ORCH_DECISION METAOS_CI_DETERMINISTIC_ORCH_OUTBOX

# gate 결과를 "receipt"로 쓰는 경로가 네 repo에서 어떤 파일인지에 따라 달라질 수 있어서,
# 가장 안전한 운영 루프: 지금처럼 "Outbox item"을 직접 만들어 Slack으로 쏘고 AlertEmitted만 봉인.
# (Orchestrator full run을 운영에 넣기 전, 경고부터 사회 연결하는 1차 목표에 최적)

# 5) outbox item을 "gate 기반 경고"로 간단 생성 (최소 outbox 스키마를 흉내)
OUTBOX_DIR="/tmp/orch_outbox_live/${SYMBOL}"
mkdir -p "$OUTBOX_DIR"
OUTBOX_ITEM="$OUTBOX_DIR/delivery_001.json"

$PY - <<PY
import json, time, hashlib, pathlib
gate=json.loads(pathlib.Path("$GATE").read_text(encoding="utf-8"))
ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

decision_sha256 = hashlib.sha256(json.dumps(gate, sort_keys=True, ensure_ascii=False, separators=(",",":")).encode("utf-8")).hexdigest()

out = {
  "schema":"orch_outbox_item.v1",
  "ts_iso": ts,
  "kind":"ORCH_OUTBOX_ITEM",
  "channel":"SENTINEL",
  "plan_id": f"live_{gate.get('event_id','unknown')}",
  "decision_sha256": decision_sha256,
  "decision_ref": f"sha256:{decision_sha256}",
  "routing_capsule_sha256": gate.get("payload",{}).get("policy_capsule_sha256",""),
  "index": 1,
  "delivery": {
    "channel":"slack",
    "target":"#sentinel-alerts",
    "template":"AUDIT_V0_3",
    "payload": gate,
  },
}
out["delivery_sha256"]=hashlib.sha256(json.dumps(out["delivery"], sort_keys=True, ensure_ascii=False, separators=(",",":")).encode("utf-8")).hexdigest()
out["outbox_item_sha256"]=hashlib.sha256(json.dumps({
  "decision_sha256": out["decision_sha256"],
  "index": out["index"],
  "delivery_sha256": out["delivery_sha256"],
}, sort_keys=True, ensure_ascii=False, separators=(",",":")).encode("utf-8")).hexdigest()

pathlib.Path("$OUTBOX_ITEM").write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")
print("OK: wrote outbox", "$OUTBOX_ITEM")
PY

# 6) slack emit (운영)
$PY "$ROOT/tools/emit_slack_alert.py" --outbox-item "$OUTBOX_ITEM"

# 7) alert emitted seal + verify
$PY "$ROOT/tools/audit_append_alert_emitted.py" --outbox-item "$OUTBOX_ITEM" --event-id "SOCIAL:ALERT_EMITTED:${SYMBOL}:1" >/dev/null
$PY "$ROOT/tools/audit/verify_chain.py" --schema "$ROOT/sdk/schemas/audit_event.v1.json" --chain "$AURALIS_AUDIT_PATH"

echo "OK: social connect cycle sealed -> $AURALIS_AUDIT_PATH"
echo "OUTBOX_ITEM=$OUTBOX_ITEM"
