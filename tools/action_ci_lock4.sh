#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
export PYTHONPATH="$ROOT"

# Determinism switch
export METAOS_CI_DETERMINISTIC_PLAN=1

# Paths
RECEIPT="/tmp/receipt_ci.json"
PLAN_DIR="/tmp/plans_ci"
QUEUE_DIR="/tmp/queues_ci"

rm -rf "$PLAN_DIR" "$QUEUE_DIR"
mkdir -p "$PLAN_DIR" "$QUEUE_DIR"

# Minimal receipt fixture (non-execution channel to avoid Gate-2)
cat > "$RECEIPT" <<'JSON'
{
  "schema": "receipt.v1",
  "proposal_id": "CI-PROP-1",
  "before_policy_version": 1,
  "after_policy_version": 1,
  "before_policy_sha256": "f81892ddcfb980739dabf994abdac86839073c6bea308df7a7c3b3e93b31dbe1",
  "after_policy_sha256": "f81892ddcfb980739dabf994abdac86839073c6bea308df7a7c3b3e93b31dbe1",
  "meta": {
    "channel": "SENTINEL"
  },
  "evidence": {
    "rationale": "CI determinism check",
    "evidence_scene_ids": ["scene_ci_1"],
    "evidence_sample_ids": ["sample_ci_1"],
    "evidence_snapshot_ids": ["snap_ci_1"]
  },
  "patch_ops": [],
  "warnings": [],
  "approvers_used": []
}
JSON

# Build+save plan twice, route queue twice, compare digests
$PY - <<'PY'
import json, hashlib, os
from core.C_action.plan_from_receipt import build_delivery_plan_from_receipt, save_delivery_plan
from core.C_action.queue_router import route_to_queue

def digest_file(path: str) -> str:
    b=open(path,"rb").read()
    return hashlib.sha256(b).hexdigest()

receipt = "/tmp/receipt_ci.json"
plan_dir = "/tmp/plans_ci"
queue_dir = "/tmp/queues_ci"

def run_once(tag: str):
    plan = build_delivery_plan_from_receipt(receipt)
    plan_path = save_delivery_plan(plan, plan_dir)
    qpath = route_to_queue(plan, plan_path, base_dir=queue_dir)
    return plan_path, qpath, digest_file(plan_path), digest_file(qpath)

p1,q1,dp1,dq1 = run_once("1")
p2,q2,dp2,dq2 = run_once("2")

print("plan1 =", p1)
print("plan2 =", p2)
print("queue1=", q1)
print("queue2=", q2)
print("plan.digest.1 =", dp1)
print("plan.digest.2 =", dp2)
print("queue.digest.1 =", dq1)
print("queue.digest.2 =", dq2)

if dp1 != dp2:
    raise SystemExit("FAIL-CLOSED: DeliveryPlan not deterministic under METAOS_CI_DETERMINISTIC_PLAN=1")
if dq1 != dq2:
    raise SystemExit("FAIL-CLOSED: queue item not deterministic under METAOS_CI_DETERMINISTIC_PLAN=1")

print("OK: LOCK4 plan+queue deterministic")
PY
