#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
export PYTHONPATH="$ROOT"

# Determinism switches
export METAOS_CI_DETERMINISTIC_PLAN=1
export METAOS_CI_DETERMINISTIC_CONSUMER=1

# Paths
RECEIPT="/tmp/receipt_ci.json"
PLAN_DIR="/tmp/plans_ci"
QUEUE_DIR="/tmp/queues_ci"

rm -rf "$PLAN_DIR" "$QUEUE_DIR"
mkdir -p "$PLAN_DIR" "$QUEUE_DIR"

# Receipt fixture (same as LOCK4)
cat > "$RECEIPT" <<'JSON'
{
  "schema": "receipt.v1",
  "proposal_id": "CI-PROP-1",
  "before_policy_version": 1,
  "after_policy_version": 1,
  "before_policy_sha256": "f81892ddcfb980739dabf994abdac86839073c6bea308df7a7c3b3e93b31dbe1",
  "after_policy_sha256": "f81892ddcfb980739dabf994abdac86839073c6bea308df7a7c3b3e93b31dbe1",
  "meta": { "channel": "SENTINEL" },
  "evidence": { "rationale": "CI determinism check" },
  "patch_ops": [],
  "warnings": [],
  "approvers_used": []
}
JSON

# Build plan and queue item
$PY - <<'PY'
from core.C_action.plan_from_receipt import build_delivery_plan_from_receipt, save_delivery_plan
from core.C_action.queue_router import route_to_queue

receipt="/tmp/receipt_ci.json"
plan_dir="/tmp/plans_ci"
queue_dir="/tmp/queues_ci"

plan=build_delivery_plan_from_receipt(receipt)
plan_path=save_delivery_plan(plan, plan_dir)
qpath=route_to_queue(plan, plan_path, base_dir=queue_dir)

print("PLAN_PATH=", plan_path)
print("QUEUE_ITEM=", qpath)
PY

QUEUE_ITEM="$(python - <<'PY'
import glob
paths=glob.glob("/tmp/queues_ci/*/pending/*.json")
print(paths[0])
PY
)"

# Consume twice from two copies (determinism check)
cp "$QUEUE_ITEM" /tmp/q1.json
cp "$QUEUE_ITEM" /tmp/q2.json

OUT1="$($PY - <<PY
from core.C_action.queue_consumer import consume_one
print(consume_one("/tmp/q1.json", base_dir="/tmp/queues_ci"))
PY
)"
OUT2="$($PY - <<PY
from core.C_action.queue_consumer import consume_one
print(consume_one("/tmp/q2.json", base_dir="/tmp/queues_ci"))
PY
)"

# Compare digests
$PY - <<PY
import hashlib
def digest(p):
    return hashlib.sha256(open(p,"rb").read()).hexdigest()
o1="$OUT1"; o2="$OUT2"
d1=digest(o1); d2=digest(o2)
print("processed1 =", o1)
print("processed2 =", o2)
print("digest1 =", d1)
print("digest2 =", d2)
if d1!=d2:
    raise SystemExit("FAIL-CLOSED: processed artifact not deterministic under METAOS_CI_DETERMINISTIC_CONSUMER=1")
print("OK: processed deterministic")
PY

# AuditChain seal + verify
export AURALIS_AUDIT_PATH="/tmp/audit_ci_lock5.jsonl"
rm -f "$AURALIS_AUDIT_PATH"

$PY tools/audit_append_processed_chain.py --processed "$OUT1" --ts 0 --event-id "CI:QUEUE_PROCESSED:SENTINEL:1" >/dev/null

$PY tools/audit/verify_chain.py --schema sdk/schemas/audit_event.v1.json --chain "$AURALIS_AUDIT_PATH"

echo "OK: LOCK5 consumer+audit verified"
