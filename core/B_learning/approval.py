from __future__ import annotations

import json
import os
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.policy_store.store import PolicyStore, sha256_of_obj


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def jsonl_append(path: str, record: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def jsonl_read(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


# ---------- JSON Patch helpers (minimal) ----------
# (이전과 동일, 생략)


def _unescape(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def _split_pointer(path: str) -> List[str]:
    if path == "" or path == "/":
        return []
    if not path.startswith("/"):
        raise ValueError(f"Invalid JSON pointer: {path}")
    return [_unescape(p) for p in path.lstrip("/").split("/") if p != ""]


def _get_parent_and_key(doc: Any, pointer: str) -> Tuple[Any, str]:
    parts = _split_pointer(pointer)
    if not parts:
        raise ValueError("Pointer refers to document root")
    parent_parts = parts[:-1]
    key = parts[-1]
    cur = doc
    for p in parent_parts:
        if isinstance(cur, list):
            cur = cur[int(p)]
        else:
            cur = cur[p]
    return cur, key


def _get(doc: Any, pointer: str) -> Any:
    cur = doc
    for p in _split_pointer(pointer):
        if isinstance(cur, list):
            cur = cur[int(p)]
        else:
            cur = cur[p]
    return cur


def _exists(doc: Any, pointer: str) -> bool:
    try:
        _get(doc, pointer)
        return True
    except Exception:
        return False


def apply_patch(doc: Any, ops: List[Dict[str, Any]]) -> Any:
    new_doc = json.loads(json.dumps(doc))
    for op in ops:
        kind = op.get("op")
        path = op.get("path")
        if kind not in ("add", "replace", "remove"):
            raise ValueError(f"Unsupported op: {kind}")
        if not isinstance(path, str):
            raise ValueError("Patch op missing string 'path'")
        if path in ("", "/"):
            raise ValueError("Root patch not allowed")

        if kind in ("add", "replace"):
            if "value" not in op:
                raise ValueError(f"{kind} op missing 'value'")
            value = op["value"]

        if kind == "add":
            parent, key = _get_parent_and_key(new_doc, path)
            if isinstance(parent, list):
                if key == "-":
                    parent.append(value)
                else:
                    parent.insert(int(key), value)
            else:
                parent[key] = value

        elif kind == "replace":
            if not _exists(new_doc, path):
                raise ValueError(f"replace path does not exist: {path}")
            parent, key = _get_parent_and_key(new_doc, path)
            if isinstance(parent, list):
                parent[int(key)] = value
            else:
                parent[key] = value

        elif kind == "remove":
            if not _exists(new_doc, path):
                raise ValueError(f"remove path does not exist: {path}")
            parent, key = _get_parent_and_key(new_doc, path)
            if isinstance(parent, list):
                parent.pop(int(key))
            else:
                parent.pop(key, None)

    return new_doc


# ---------- v0.2 Approval records ----------


@dataclass(frozen=True)
class ApprovalRecord:
    proposal_id: str
    decision: str  # "approved" | "rejected"
    reviewer: str
    ts_iso: str
    comment: str
    policy_target_sha256: Optional[str] = None
    status: str = "PENDING"  # PENDING | APPLIED | REJECTED | APPLIED_NOOP
    before_version: Optional[int] = None
    before_sha256: Optional[str] = None
    after_version: Optional[int] = None
    after_sha256: Optional[str] = None
    receipt_hash: Optional[str] = None


def write_approval(approvals_jsonl: str, rec: ApprovalRecord) -> None:
    jsonl_append(approvals_jsonl, rec.__dict__)


def approvals_for(approvals_jsonl: str, proposal_id: str) -> List[Dict[str, Any]]:
    return [r for r in jsonl_read(approvals_jsonl) if r.get("proposal_id") == proposal_id]


def find_proposal(proposals_jsonl: str, proposal_id: str) -> Dict[str, Any]:
    for rec in jsonl_read(proposals_jsonl):
        if rec.get("proposal_id") == proposal_id:
            return rec
    raise KeyError(f"proposal_id not found: {proposal_id}")


def dry_run_validate(proposal: Dict[str, Any], current_policy: Dict[str, Any]) -> Dict[str, Any]:
    patch_ops = proposal.get("patch_ops")
    if not isinstance(patch_ops, list) or not patch_ops:
        raise ValueError("proposal.patch_ops missing or empty list")

    base_hash = proposal.get("policy_target_sha256")
    latest_hash = sha256_of_obj(current_policy)

    warnings: List[str] = []
    if base_hash and base_hash != latest_hash:
        warnings.append("BASE_POLICY_HASH_MISMATCH")

    patched = apply_patch(current_policy, patch_ops)
    return {
        "warnings": warnings,
        "before_sha256": latest_hash,
        "after_sha256": sha256_of_obj(patched),
        "patched_policy": patched,
    }


# ---------- v0.2 flows ----------


def approve_only(
    approvals_jsonl: str,
    proposals_jsonl: str,
    proposal_id: str,
    reviewer: str,
    comment: str,
) -> ApprovalRecord:
    proposal = find_proposal(proposals_jsonl, proposal_id)
    rec = ApprovalRecord(
        proposal_id=proposal_id,
        decision="approved",
        reviewer=reviewer,
        ts_iso=now_iso(),
        comment=comment,
        policy_target_sha256=proposal.get("policy_target_sha256"),
        status="PENDING",
    )
    write_approval(approvals_jsonl, rec)
    return rec


def apply_after_approvals(
    approvals_jsonl: str,
    proposals_jsonl: str,
    applied_receipts_dir: str,
    policy_dir: str,
    proposal_id: str,
    applier: str,
    comment: str,
    min_approvals: int = 1,
    strategy: str = "reject",  # reject | force | rebase
) -> ApprovalRecord:
    approvals = approvals_for(approvals_jsonl, proposal_id)

    pending_approvers = {
        a.get("reviewer")
        for a in approvals
        if a.get("decision") == "approved" and a.get("status") == "PENDING" and a.get("reviewer")
    }

    if min_approvals >= 2 and applier in pending_approvers:
        raise RuntimeError(
            "Self-approve not allowed when min_approvals >= 2 (applier is already a PENDING approver)"
        )

    if len(pending_approvers) < min_approvals:
        raise RuntimeError(f"Need {min_approvals} approvals, got {len(pending_approvers)}")

    store = PolicyStore(policy_dir)
    latest = store.latest()
    proposal = find_proposal(proposals_jsonl, proposal_id)

    result = dry_run_validate(proposal, latest.policy)

    # ts_tag 생성 (파일명 중복 방지용)
    ts_tag = now_iso().replace(":", "").replace("-", "").replace(".", "")
    ts_tag = ts_tag.replace("+", "").replace("Z", "")

    mismatch = "BASE_POLICY_HASH_MISMATCH" in result["warnings"]

    if mismatch and strategy == "reject":
        raise RuntimeError("Base hash mismatch; strategy=reject")

    before_sha = result["before_sha256"]
    after_sha = result["after_sha256"]

       # ---------------------------
    # CHANNEL/EVIDENCE NORMALIZATION (v0.2.3)
    # - keep channel available for C-line routing
    # - ensure evidence is a dict and evidence.channel is set
    # ---------------------------
    evidence_block = proposal.get("evidence") or {}
    if not isinstance(evidence_block, dict):
        evidence_block = {"_raw": evidence_block}

    channel = proposal.get("channel") or evidence_block.get("channel")

    # === fallback: infer channel from patch_ops JSON pointer (/thresholds/<channel>/...) ===
    if channel is None:
        ops = proposal.get("patch_ops") or []
        if isinstance(ops, list):
            for op in ops:
                path = (op or {}).get("path")
                if isinstance(path, str) and path.startswith("/thresholds/"):
                    parts = [p for p in path.split("/") if p]  # ["thresholds", "<channel>", ...]
                    if len(parts) >= 2:
                        inferred = parts[1]
                        # allow common channel id charset: letters/digits/_/-
                        ok = True
                        for ch in inferred:
                            if not (ch.isalnum() or ch in "_-"):
                                ok = False
                                break
                        if ok and inferred:
                            channel = inferred
                            break
    # ============================================================================

    if channel is not None:
        evidence_block = dict(evidence_block)
        evidence_block["channel"] = channel


    # ---------------------------
    # NO-OP GUARD (v0.2.1) - 파일명에 ts_tag 추가
    # ---------------------------
    if after_sha == before_sha:
        receipt = {
            "proposal_id": proposal_id,
            "applier": applier,
            "ts_iso": now_iso(),
            "comment": comment,
            "channel": channel,
            "before_policy_version": latest.version,
            "before_policy_sha256": latest.sha256,
            "after_policy_version": latest.version,
            "after_policy_sha256": latest.sha256,
            "artifact_hash": proposal.get("artifact_hash"),
            "warnings": result["warnings"],
            "patch_ops": proposal.get("patch_ops"),
            "evidence": evidence_block,
            "strategy": strategy,
            "NOOP_APPLY": True,
            "reason": "after_sha256 == before_sha256",
            "approvers_used": sorted(pending_approvers),
            "min_approvals": min_approvals,
        }

        os.makedirs(applied_receipts_dir, exist_ok=True)
        rpath = os.path.join(
            applied_receipts_dir,
            f"receipt_{proposal_id}_noop_v{latest.version:04d}_{ts_tag}.json",  # ← ts_tag 추가
        )
        with open(rpath, "w", encoding="utf-8") as f:
            json.dump(receipt, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        rhash = hashlib.sha256(_canonical_json_bytes(receipt)).hexdigest()

        rec = ApprovalRecord(
            proposal_id=proposal_id,
            decision="approved",
            reviewer=applier,
            ts_iso=now_iso(),
            comment=comment,
            policy_target_sha256=proposal.get("policy_target_sha256"),
            status="APPLIED_NOOP",
            before_version=latest.version,
            before_sha256=latest.sha256,
            after_version=latest.version,
            after_sha256=latest.sha256,
            receipt_hash=rhash,
        )
        write_approval(approvals_jsonl, rec)
        return rec

    # 실제 변경 시 - 파일명에 ts_tag 추가
    patched = result["patched_policy"]
    new_snap = store.save_new_version(patched)

    receipt = {
        "proposal_id": proposal_id,
        "applier": applier,
        "ts_iso": now_iso(),
        "comment": comment,
        "channel": channel,
        "before_policy_version": latest.version,
        "before_policy_sha256": latest.sha256,
        "after_policy_version": new_snap.version,
        "after_policy_sha256": new_snap.sha256,
        "artifact_hash": proposal.get("artifact_hash"),
        "warnings": result["warnings"],
        "patch_ops": proposal.get("patch_ops"),
        "evidence": evidence_block,
        "strategy": strategy,
        "NOOP_APPLY": False,
        "approvers_used": sorted(pending_approvers),
        "min_approvals": min_approvals,
    }

    os.makedirs(applied_receipts_dir, exist_ok=True)
    rpath = os.path.join(
        applied_receipts_dir,
        f"receipt_{proposal_id}_v{latest.version:04d}_to_v{new_snap.version:04d}_{ts_tag}.json",  # ← ts_tag 추가
    )
    with open(rpath, "w", encoding="utf-8") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")

    rhash = hashlib.sha256(_canonical_json_bytes(receipt)).hexdigest()

    rec = ApprovalRecord(
        proposal_id=proposal_id,
        decision="approved",
        reviewer=applier,
        ts_iso=now_iso(),
        comment=comment,
        policy_target_sha256=proposal.get("policy_target_sha256"),
        status="APPLIED",
        before_version=latest.version,
        before_sha256=latest.sha256,
        after_version=new_snap.version,
        after_sha256=new_snap.sha256,
        receipt_hash=rhash,
    )
    write_approval(approvals_jsonl, rec)

    return rec