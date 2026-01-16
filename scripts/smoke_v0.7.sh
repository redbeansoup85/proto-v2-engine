#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8010}"
DATA_DIR="${METAOS_DATA_DIR:-var/metaos}"

ts="$(date +%s)"
DPA_ID="dpa_smoke_v0_6_${ts}"
EVT_ID="evt_smoke_v0_6_${ts}"
APR_ID="apr_smoke_v0_6_${ts}"

echo "[v0.7 smoke] BASE_URL=${BASE_URL}"
echo "[v0.7 smoke] DATA_DIR=${DATA_DIR}"

echo "== health =="
curl -fsS "${BASE_URL}/health" >/dev/null

echo "== enqueue approval =="
curl -fsS -X POST "${BASE_URL}/v1/constitutional/approvals/enqueue" \
  -H 'Content-Type: application/json' \
  -d "{
    \"approval_id\":\"${APR_ID}\",
    \"dpa_id\":\"${DPA_ID}\",
    \"event_id\":\"${EVT_ID}\",
    \"selected_option_id\":\"opt_approve\",
    \"authority_id\":\"human_admin\",
    \"rationale_ref\":\"ui://constitutional/transition\"
  }" >/dev/null

echo "== approve =="
curl -fsS -X POST "${BASE_URL}/v1/constitutional/approvals/${APR_ID}/approve" >/dev/null

echo "== transition =="
resp="$(curl -sS -w "\nHTTP_CODE=%{http_code}\n" -X POST "${BASE_URL}/v1/constitutional/transition" \
  -H 'Content-Type: application/json' \
  -d "{
    \"approval_id\":\"${APR_ID}\",
    \"dpa_id\":\"${DPA_ID}\",
    \"event_id\":\"${EVT_ID}\",
    \"prelude_output\": {
      \"org_id\": \"org_demo_001\",
      \"site_id\": \"site_demo_001\",
      \"ts_start_iso\": \"2026-01-16T08:00:00Z\",
      \"ts_end_iso\": \"2026-01-16T08:05:00Z\",
      \"mode\": \"observe\",
      \"severity\": \"low\",
      \"reasons\": [\"v0.6 smoke minimal input\"],
      \"window_sec\": 300,
      \"missing_ratio\": 0.0,
      \"quality_score\": 1.0,
      \"anomaly_score\": 0.0,
      \"uncertainty_score\": 0.1,
      \"confidence_score\": 0.9
    },
    \"approval\": {\"decision\":\"APPROVE\"}
  }")"

echo "$resp"
code="$(echo "$resp" | sed -n "s/^HTTP_CODE=//p" | tail -n 1)"
if [ "$code" != "200" ]; then
  echo "FAIL: transition returned HTTP $code" >&2
  exit 10
fi

test -f "${DATA_DIR}/approvals.jsonl"
test -f "${DATA_DIR}/dpa.jsonl"

grep -q "\"approval_id\": \"${APR_ID}\"" "${DATA_DIR}/approvals.jsonl"
grep -q "\"status\": \"APPROVED\"" "${DATA_DIR}/approvals.jsonl"

grep -q "\"dpa_id\": \"${DPA_ID}\"" "${DATA_DIR}/dpa.jsonl"
grep -q "\"status\": \"APPLIED\"" "${DATA_DIR}/dpa.jsonl"

echo
echo "SMOKE_OK: v0.7 approval queue + file persistence + transition gate"

echo "== ports contract =="
python - <<'PY'
from core.judgment.ports import DpaApplyPort
from core.judgment.persistence.noop_apply_port import NoopDpaApplyPort

p = NoopDpaApplyPort()
assert hasattr(p, "get_dpa") and hasattr(p, "apply")
assert isinstance(p, DpaApplyPort)  # runtime_checkable protocol
print("OK: ports contract present (NoopDpaApplyPort satisfies DpaApplyPort)")
PY

echo "== ports contract =="
python - <<'PY'
from core.judgment.ports import DpaApplyPort
from core.judgment.persistence.noop_apply_port import NoopDpaApplyPort

p = NoopDpaApplyPort()
assert hasattr(p, "get_dpa") and hasattr(p, "apply")
assert isinstance(p, DpaApplyPort)  # runtime_checkable protocol
print("OK: ports contract present (NoopDpaApplyPort satisfies DpaApplyPort)")
PY
