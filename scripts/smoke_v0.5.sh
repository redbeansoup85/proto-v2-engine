#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8010}"
BASE="http://127.0.0.1:${PORT}"

echo "[1] pytest..."
pytest -q tests/test_constitutional_guards.py
pytest -q tests/test_dpa_transitions.py

echo "[2] start uvicorn (background)..."
uvicorn infra.api.app:app --port "${PORT}" >/tmp/metaos_v0_5.log 2>&1 &
PID=$!
sleep 1

cleanup() {
  kill -9 "${PID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[3] openapi has constitutional transition..."
curl -s "${BASE}/openapi.json" | python -c 'import json,sys; d=json.load(sys.stdin); assert "/v1/constitutional/transition" in d.get("paths", {}); print("[OK] openapi path present")'

echo "[4] approve path (seed -> transition)..."
python - <<'PY'
import json, subprocess
from pathlib import Path

d=json.loads(Path("docs/demo/v0_3_childcare.json").read_text(encoding="utf-8"))

# seed => APPROVED
subprocess.run(
 ["curl","-s","-X","POST","http://127.0.0.1:8010/v1/constitutional/__debug_seed",
  "-H","Content-Type: application/json",
  "-d", json.dumps({"dpa_id":"dpa_demo_001","event_id":"evt_demo_001","selected_option_id":"opt_approve"})],
 check=True
)

payload = {
  "dpa_id": "dpa_demo_001",
  "event_id": "evt_demo_001",
  "prelude_output": d,
  "approval": {"decision":"APPROVE","authority_id":"human_001","immutable":True,"rationale_ref":"ui://constitutional/transition"},
  "human_decision": {
    "selected_option_id":"opt_approve",
    "reason_codes":["SMOKE"],
    "reason_note":"v0.5 smoke",
    "approver_name":"Tester",
    "approver_role":"Owner",
    "signature":"Tester@local"
  }
}

p=subprocess.run(
 ["curl","-s","-i","-X","POST","http://127.0.0.1:8010/v1/constitutional/transition",
  "-H","Content-Type: application/json","-d", json.dumps(payload)],
 capture_output=True,text=True
)
print(p.stdout)
assert "200 OK" in p.stdout and '"ok":true' in p.stdout
print("[OK] approve flow passed")

# reject => 403
payload2 = {
  "dpa_id":"dpa_demo_002",
  "event_id":"evt_demo_002",
  "prelude_output": d,
  "approval":{"decision":"REJECT","authority_id":"human_001","immutable":True,"rationale_ref":"ui://constitutional/transition"},
}
p2=subprocess.run(
 ["curl","-s","-i","-X","POST","http://127.0.0.1:8010/v1/constitutional/transition",
  "-H","Content-Type: application/json","-d", json.dumps(payload2)],
 capture_output=True,text=True
)
print(p2.stdout)
assert "403 Forbidden" in p2.stdout and "Rejected (immutable)" in p2.stdout
print("[OK] reject flow blocked as expected")
PY

echo "[DONE] smoke_v0.5 OK"
