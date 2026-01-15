from __future__ import annotations

import hashlib
import json
import os
import uuid
import warnings
from typing import Any, Dict, List, Optional, Tuple

from core.B_learning.approval import _canonical_json_bytes, now_iso
from core.C_action.contracts import DeliveryPlan
from core.C_action.execution_gate import EXECUTION_CHANNELS
from core.contracts.orchestrator import (
    ExecutionAuthorizationRequest,
    ResponsibilityAcceptance,
    ExecutionScope,
    ExecutionLimit,
    ExecutionTimebox,
    assert_execution_request_valid,
)


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def sha256_of_obj(obj: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(obj)).hexdigest()


def _truthy_env(name: str) -> bool:
    v = os.getenv(name, "").strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def _extract_channel(receipt: Dict[str, Any], receipt_path: str) -> str:
    """
    Routing-key constitution:

    - SSoT: receipt.meta.channel
    - Legacy compatibility: receipt.channel (DEPRECATED; warn)
    - evidence.channel: FORBIDDEN by default
      - allowed only if METAOS_LEGACY_EVIDENCE_CHANNEL_OK=1 (recovery mode)
    """
    meta = receipt.get("meta") or {}
    if isinstance(meta, dict):
        ch = meta.get("channel") or meta.get("Channel")
        if isinstance(ch, str) and ch.strip():
            return ch.strip()

    # root channel (legacy compat) -> warn, but allow
    root_ch = receipt.get("channel") or receipt.get("Channel")
    if isinstance(root_ch, str) and root_ch.strip():
        warnings.warn(
            f"[DEPRECATED] receipt.channel used as routing key; migrate to receipt.meta.channel. path={receipt_path}",
            DeprecationWarning,
        )
        return root_ch.strip()

    # evidence channel is forbidden unless explicit recovery mode
    evidence = receipt.get("evidence") or {}
    ev_ch = None
    if isinstance(evidence, dict):
        ev_ch = evidence.get("channel") or evidence.get("Channel")
    if isinstance(ev_ch, str) and ev_ch.strip():
        if _truthy_env("METAOS_LEGACY_EVIDENCE_CHANNEL_OK"):
            warnings.warn(
                f"[RECOVERY] Using evidence.channel (deprecated). Immediately migrate to meta.channel. path={receipt_path}",
                RuntimeWarning,
            )
            return ev_ch.strip()
        raise ValueError(
            "evidence.channel is not allowed as routing key "
            "(set METAOS_LEGACY_EVIDENCE_CHANNEL_OK=1 only for controlled recovery)"
        )

    raise ValueError("receipt.meta.channel is required (unknown queue disabled)")


def _enforce_execution_gate_from_receipt(receipt: Dict[str, Any], receipt_path: str, channel: str) -> None:
    """
    Gate-2 enforcement at plan-build time.
    If channel is execution-class, receipt.meta.execution_request_path must exist and be valid.

    v1.0 invariant:
    - execution_request.judgment_ref MUST equal receipt_path (SSoT)
    """
    if channel not in EXECUTION_CHANNELS:
        return

    meta = receipt.get("meta") or {}
    if not isinstance(meta, dict):
        meta = {}

    exec_req_path = meta.get("execution_request_path")
    if not exec_req_path or not isinstance(exec_req_path, str):
        raise ValueError(
            f"ExecutionAuthorization required for channel={channel}: "
            f"missing receipt.meta.execution_request_path. receipt_path={receipt_path}"
        )

    if not os.path.exists(exec_req_path):
        raise ValueError(
            f"execution_request_path does not exist: {exec_req_path}. receipt_path={receipt_path}"
        )

    raw = load_json(exec_req_path)
    if not isinstance(raw, dict):
        raise ValueError(f"execution_request must be a JSON object. path={exec_req_path}")

    # --- explicit reconstruction (NO implicit magic) ---
    resp_raw = raw.get("responsibility")
    if not isinstance(resp_raw, dict):
        raise ValueError("execution_request.responsibility must be an object")
    responsibility = ResponsibilityAcceptance(**resp_raw)

    scope_raw = raw.get("scope")
    if not isinstance(scope_raw, dict):
        raise ValueError("execution_request.scope must be an object")
    scope = ExecutionScope(**scope_raw)

    limit_raw = raw.get("limit")
    if not isinstance(limit_raw, dict):
        raise ValueError("execution_request.limit must be an object")
    limit = ExecutionLimit(**limit_raw)

    timebox_raw = raw.get("timebox")
    if not isinstance(timebox_raw, dict):
        raise ValueError("execution_request.timebox must be an object")
    timebox = ExecutionTimebox(**timebox_raw)

    req = ExecutionAuthorizationRequest(
        auto_action=raw.get("auto_action", False),
        responsibility=responsibility,
        scope=scope,
        limit=limit,
        timebox=timebox,
        judgment_ref=str(raw.get("judgment_ref") or ""),
        request_payload=raw.get("request_payload"),
        metadata=raw.get("metadata"),
    )

    # Gate-2 invariants (structure + responsibility acceptance)
    assert_execution_request_valid(req)

    # Strong v1.0 lock: judgment_ref must point to the receipt itself
    if req.judgment_ref != receipt_path:
        raise ValueError(
            f"judgment_ref mismatch: req.judgment_ref={req.judgment_ref} "
            f"!= receipt_path={receipt_path}"
        )


def build_delivery_plan_from_receipt(receipt_path: str) -> DeliveryPlan:
    r = load_json(receipt_path)
    rhash = sha256_of_obj(r)

    evidence = r.get("evidence") or {}
    patch_ops = r.get("patch_ops") or []

    warnings_list = r.get("warnings") or []
    if not isinstance(warnings_list, list):
        warnings_list = [str(warnings_list)]
    warnings_list = [str(x) for x in warnings_list]

    # Promote evidence links
    evidence_sample_ids = evidence.get("evidence_sample_ids") or []
    evidence_scene_ids = evidence.get("evidence_scene_ids") or []
    evidence_snapshot_ids = evidence.get("evidence_snapshot_ids") or []

    if not isinstance(evidence_sample_ids, list):
        evidence_sample_ids = [str(evidence_sample_ids)]
    if not isinstance(evidence_scene_ids, list):
        evidence_scene_ids = [str(evidence_scene_ids)]
    if not isinstance(evidence_snapshot_ids, list):
        evidence_snapshot_ids = [str(evidence_snapshot_ids)]

    evidence_sample_ids = [str(x) for x in evidence_sample_ids]
    evidence_scene_ids = [str(x) for x in evidence_scene_ids]
    evidence_snapshot_ids = [str(x) for x in evidence_snapshot_ids]

    noop = bool(r.get("NOOP_APPLY") is True)

    summary = "Policy patch applied" if not noop else "No-op apply (policy unchanged)"
    rationale = str((evidence.get("rationale") if isinstance(evidence, dict) else None) or r.get("reason") or "n/a")

    approvers_used = r.get("approvers_used") or []
    if not isinstance(approvers_used, list):
        approvers_used = [str(approvers_used)]
    approvers_used = [str(x) for x in approvers_used]

    rec_actions: List[Dict[str, Any]] = []
    if patch_ops:
        rec_actions.append({"type": "REVIEW_POLICY_CHANGE", "notes": f"{len(patch_ops)} JSONPatch ops"})
    rec_actions.append({"type": "MONITOR_NEXT_WINDOW", "notes": "Observe next window and generate new LearningSample + proposals"})

    # channel enforcement (unknown queue disabled)
    channel = _extract_channel(r, receipt_path=receipt_path)

    # Gate-2 enforcement (only for execution-class channels)
    _enforce_execution_gate_from_receipt(r, receipt_path=receipt_path, channel=channel)

    plan = DeliveryPlan(
        plan_id="dp_" + uuid.uuid4().hex,
        ts_iso=now_iso(),
        channel=channel,
        proposal_id=str(r.get("proposal_id") or ""),
        receipt_path=receipt_path,
        receipt_hash=rhash,
        policy_version=int(r.get("after_policy_version") or r.get("before_policy_version") or 0),
        policy_sha256=str(r.get("after_policy_sha256") or ""),
        status="READY",
        summary=summary,
        rationale=rationale,
        warnings=warnings_list,
        evidence=evidence,
        evidence_sample_ids=evidence_sample_ids,
        evidence_scene_ids=evidence_scene_ids,
        evidence_snapshot_ids=evidence_snapshot_ids,
        patch_ops=patch_ops,
        approvers_used=approvers_used,
        applier=str(r.get("applier") or "") or None,
        strategy=str(r.get("strategy") or "") or None,
        noop_apply=noop,
        recommended_actions=rec_actions,
    )
    return plan


def save_delivery_plan(plan: DeliveryPlan, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{plan.plan_id}.json")
    obj = plan.__dict__
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)
    return path


def append_delivery_index(plan: DeliveryPlan, plan_path: str, index_path: str) -> None:
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    row = {
        "plan_id": plan.plan_id,
        "ts_iso": plan.ts_iso,
        "proposal_id": plan.proposal_id,
        "channel": plan.channel,
        "policy_version": plan.policy_version,
        "policy_sha256": plan.policy_sha256,
        "noop_apply": plan.noop_apply,
        "warnings": plan.warnings,
        "approvers_used": plan.approvers_used,
        "receipt_hash": plan.receipt_hash,
        "receipt_path": plan.receipt_path,
        "plan_path": plan_path,
        "evidence_scene_ids": plan.evidence_scene_ids,
        "evidence_sample_ids": plan.evidence_sample_ids,
        "evidence_snapshot_ids": plan.evidence_snapshot_ids,
        "patch_ops_count": len(plan.patch_ops or []),
    }
    with open(index_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
        f.write("\n")


def build_delivery_pack(plan: DeliveryPlan, plan_path: str) -> Dict[str, Any]:
    headline = f"[Meta-OS] DeliveryPlan READY: {plan.proposal_id} (v{plan.policy_version:04d})"
    if plan.noop_apply:
        headline += " [NOOP]"
    if plan.warnings:
        headline += f" [WARN:{len(plan.warnings)}]"

    body_lines = [
        f"plan_id: {plan.plan_id}",
        f"proposal_id: {plan.proposal_id}",
        f"policy: v{plan.policy_version:04d} sha={plan.policy_sha256[:12]}…",
        f"noop_apply: {plan.noop_apply}",
        f"approvers_used: {', '.join(plan.approvers_used) if plan.approvers_used else 'n/a'}",
        f"warnings: {', '.join(plan.warnings) if plan.warnings else 'none'}",
        f"rationale: {plan.rationale}",
        f"plan_path: {plan_path}",
        f"receipt_path: {plan.receipt_path}",
    ]
    if plan.evidence_scene_ids:
        body_lines.append(f"scene_ids: {', '.join(plan.evidence_scene_ids)}")
    if plan.evidence_sample_ids:
        body_lines.append(f"sample_ids: {', '.join(plan.evidence_sample_ids)}")
    if plan.evidence_snapshot_ids:
        body_lines.append(f"snapshot_ids: {', '.join(plan.evidence_snapshot_ids)}")

    pack = {
        "type": "DELIVERY_PACK",
        "ts_iso": plan.ts_iso,
        "headline": headline,
        "text": "\n".join(body_lines),
        "payload": {
            "plan": plan.__dict__,
            "plan_path": plan_path,
        },
        "targets_suggested": [
            {"type": "slack", "channel": "#ops"},
            {"type": "email", "to": "ops@example.com"},
            {"type": "webhook", "name": "delivery-ingest"},
        ],
    }
    return pack


def save_delivery_pack(pack: Dict[str, Any], out_dir: str, plan_id: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"pack_{plan_id}.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(pack, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)
    return path


def plan_and_pack_from_receipt(
    receipt_path: str,
    plans_dir: str,
    index_path: str,
    packs_dir: str,
) -> Tuple[DeliveryPlan, str, str]:
    plan = build_delivery_plan_from_receipt(receipt_path)
    plan_path = save_delivery_plan(plan, plans_dir)
    append_delivery_index(plan, plan_path, index_path)
    pack = build_delivery_pack(plan, plan_path)
    pack_path = save_delivery_pack(pack, packs_dir, plan.plan_id)
    return plan, plan_path, pack_path


def plan_pack_queue_bundle_from_receipt(
    receipt_path: str,
    plans_dir: str,
    index_path: str,
    packs_dir: str,
    queue_base_dir: str = "logs/queues",
    bundle_base_dir: str = "logs/bundles",
):
    """
    receipt -> plan -> index -> pack -> queue item -> scene bundles
    """
    from core.C_action.queue_router import route_to_queue, write_scene_bundles

    plan, plan_path, pack_path = plan_and_pack_from_receipt(
        receipt_path=receipt_path,
        plans_dir=plans_dir,
        index_path=index_path,
        packs_dir=packs_dir,
    )

    queue_path = route_to_queue(plan, plan_path, base_dir=queue_base_dir)
    bundle_paths = write_scene_bundles(plan, plan_path, base_dir=bundle_base_dir)

    return plan, plan_path, pack_path, queue_path, bundle_paths
