from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from core.C_action.contracts import DeliveryPlan
from core.C_action.execution_gate import enforce_execution_gate_for_queue_item


def _save_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _extract_execution_request_path_from_receipt(receipt_path: Optional[str]) -> Optional[str]:
    """
    Pull execution_request_path from receipt JSON.
    Supported locations:
      - receipt.meta.execution_request_path  (preferred)
      - receipt.execution_request_path       (legacy)
    """
    if not receipt_path or not isinstance(receipt_path, str):
        return None
    if not os.path.exists(receipt_path):
        return None

    try:
        r = _load_json(receipt_path)
    except Exception:
        return None

    meta = r.get("meta") or {}
    p = meta.get("execution_request_path") or r.get("execution_request_path")
    if isinstance(p, str) and p.strip():
        return p.strip()
    return None


def route_to_queue(
    plan: DeliveryPlan,
    plan_path: str,
    base_dir: str = "logs/queues",
) -> str:
    """
    Action-free queue artifact:
      logs/queues/<channel>/pending/<plan_id>.json

    NOTE:
    - unknown queue disabled: channel is mandatory.
    - Gate 2 (Execution Authorization) is enforced here for execution-class channels.
      If channel requires execution authorization, queue emission is blocked unless a valid
      ExecutionAuthorizationRequest artifact path exists (via receipt.meta.execution_request_path).
    """
    channel = plan.channel
    if not channel:
        raise ValueError("DeliveryPlan.channel is required (unknown queue disabled)")

    out_path = os.path.join(base_dir, channel, "pending", f"{plan.plan_id}.json")

    # ----------------------------
    # Gate 2 enforcement (queue-time)
    # ----------------------------
    exec_req_path = _extract_execution_request_path_from_receipt(plan.receipt_path)

    # We validate by constructing a minimal queue item stub that the gate understands.
    # If channel is NOT an execution channel, the gate returns immediately (no cost).
    gate_stub = {
        "channel": channel,
        "meta": {"execution_request_path": exec_req_path} if exec_req_path else {},
        "receipt_path": plan.receipt_path,
        "plan_path": plan_path,
        "plan_id": plan.plan_id,
    }
    enforce_execution_gate_for_queue_item(gate_stub)

    payload = {
        "queue_item_type": "DELIVERY_PLAN",
        "channel": channel,
        "status": "PENDING",
        "plan_id": plan.plan_id,
        "proposal_id": plan.proposal_id,
        "ts_iso": plan.ts_iso,
        "policy_version": plan.policy_version,
        "policy_sha256": plan.policy_sha256,
        "noop_apply": plan.noop_apply,
        "warnings": plan.warnings,
        "approvers_used": plan.approvers_used,
        "plan_path": plan_path,
        "receipt_path": plan.receipt_path,
        "evidence_scene_ids": plan.evidence_scene_ids,
        "evidence_sample_ids": plan.evidence_sample_ids,
        "evidence_snapshot_ids": plan.evidence_snapshot_ids,
        # ✅ Persist the exec authorization pointer for audit + consumer re-check
        "meta": {
            "execution_request_path": exec_req_path
        } if exec_req_path else {},
    }

    _save_json(out_path, payload)
    return out_path


def write_scene_bundles(
    plan: DeliveryPlan,
    plan_path: str,
    packs: Optional[List[Dict[str, Any]]] = None,
    base_dir: str = "logs/bundles",
) -> List[str]:
    """
    If evidence_scene_ids exist, emit one bundle per scene:
      logs/bundles/<channel>/scene_<scene_id>.json

    NOTE:
    - evidence_scene_ids sometimes come as "scene_<uuid>".
      We normalize to avoid "scene_scene_<uuid>.json".
    - Bundles are append/merge-friendly: keep last_plan_id and a small tail list.
    """
    scene_ids = plan.evidence_scene_ids or []
    if not scene_ids:
        return []

    channel = plan.channel
    if not channel:
        raise ValueError("DeliveryPlan.channel is required (unknown queue disabled)")

    out_paths: List[str] = []

    for sid in scene_ids:
        sid_clean = sid[len("scene_") :] if isinstance(sid, str) and sid.startswith("scene_") else sid
        path = os.path.join(base_dir, channel, f"scene_{sid_clean}.json")

        existing: Dict[str, Any] = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = {}

        tail = existing.get("plans_tail") or []
        if not isinstance(tail, list):
            tail = []

        tail.append(
            {
                "plan_id": plan.plan_id,
                "ts_iso": plan.ts_iso,
                "proposal_id": plan.proposal_id,
                "plan_path": plan_path,
                "policy_version": plan.policy_version,
                "noop_apply": plan.noop_apply,
                "warnings": plan.warnings,
            }
        )
        tail = tail[-20:]  # keep last 20

        bundle = {
            "bundle_type": "SCENE_BUNDLE",
            "scene_id": sid,
            "channel": channel,
            "last_ts_iso": plan.ts_iso,
            "last_plan_id": plan.plan_id,
            "plans_tail": tail,
        }

        _save_json(path, bundle)
        out_paths.append(path)

    return out_paths
