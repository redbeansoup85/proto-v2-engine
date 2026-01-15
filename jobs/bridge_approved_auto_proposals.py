# jobs/bridge_approved_auto_proposals.py
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Set

from core.policy_store.store import PolicyStore
from core.B_learning.approval import dry_run_validate  # noop detection


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir(p: str) -> None:
    d = os.path.dirname(p)
    if d:
        os.makedirs(d, exist_ok=True)


def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    if not path or not os.path.exists(path):
        return []
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
    return out


def _append_jsonl(path: str, item: Dict[str, Any]) -> None:
    _ensure_dir(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _sha256_json(obj: Any) -> str:
    s = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _merge_approval_queue_records(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Accepts append-only approval queue records and returns merged latest views:
      { approval_id: merged_item }

    Supports:
    - enqueue record: record_type == "APPROVAL_ENQUEUE_V1"
    - update record:  record_type == "APPROVAL_UPDATE_V1" or "APPROVAL_DECISION_V1"
    - merged views already written as "view" lines (fallback)
    """
    enq: Dict[str, Dict[str, Any]] = {}
    upd: Dict[str, Dict[str, Any]] = {}

    for r in records:
        aid = r.get("approval_id") or r.get("id")
        if not aid:
            continue

        rtype = r.get("record_type") or r.get("type") or ""

        # enqueue
        if rtype == "APPROVAL_ENQUEUE_V1" or ("proposal" in r and r.get("status") == "PENDING" and "kind" in r):
            enq[aid] = r
            continue

        # update/decision
        if rtype in ("APPROVAL_UPDATE_V1", "APPROVAL_DECISION_V1") or (
            "status" in r and "ts" in r and "approval_id" in r
        ):
            upd[aid] = r
            continue

        # fallback merged view
        if "proposal" in r and "status" in r:
            enq.setdefault(aid, r)

    merged: Dict[str, Dict[str, Any]] = {}
    for aid, base in enq.items():
        view = dict(base)
        u = upd.get(aid)
        if u:
            view["status"] = u.get("status", view.get("status"))
            view["status_updated_ts"] = u.get("ts")
            if u.get("note") is not None:
                view["status_note"] = u.get("note")
            if u.get("reviewer_id") is not None:
                view["reviewer_id"] = u.get("reviewer_id")
            if u.get("reviewer_role") is not None:
                view["reviewer_role"] = u.get("reviewer_role")
        merged[aid] = view

    return merged


def _load_existing_proposal_ids(proposals_jsonl: str) -> Set[str]:
    rows = _read_jsonl(proposals_jsonl)
    return {str(r.get("proposal_id")) for r in rows if r.get("proposal_id")}


def _normalize_patch_ops(auto_proposal: Dict[str, Any]) -> List[Dict[str, Any]]:
    patch = auto_proposal.get("patch")
    if isinstance(patch, list):
        return [x for x in patch if isinstance(x, dict) and x.get("op") and x.get("path")]

    patch_ops = auto_proposal.get("patch_ops")
    if isinstance(patch_ops, list):
        return [x for x in patch_ops if isinstance(x, dict) and x.get("op") and x.get("path")]

    return []


def _build_evidence(auto_proposal: Dict[str, Any]) -> Dict[str, Any]:
    metrics = {
        "window_days": auto_proposal.get("window_days"),
        "sample_count": auto_proposal.get("sample_count"),
        "confirmed_count": auto_proposal.get("confirmed_count"),
        "false_alarm_rate": auto_proposal.get("false_alarm_rate"),
        "incident_rate": auto_proposal.get("incident_rate"),
    }
    return {
        "evidence_sample_ids": auto_proposal.get("evidence_sample_ids") or [],
        "evidence_scene_ids": auto_proposal.get("evidence_scene_ids") or [],
        "evidence_snapshot_ids": auto_proposal.get("evidence_snapshot_ids") or [],
        "metrics": metrics,
        "patch_type": auto_proposal.get("patch_type"),
        "patch": {
            "direction": "AUTO_PROPOSED",
            "notes": auto_proposal.get("rationale") or "",
        },
        "rationale": auto_proposal.get("rationale") or "",
        "source": "learning_os_v2",
    }


def _convert_one(
    *,
    auto_proposal: Dict[str, Any],
    policy_latest_version: int,
    policy_latest_sha256: str,
) -> Dict[str, Any]:
    ts_iso = auto_proposal.get("ts_created") or auto_proposal.get("ts") or _now_iso()
    proposal_id = auto_proposal.get("proposal_id") or f"pp_bridge_{_sha256_json(auto_proposal)[:16]}"

    patch_ops = _normalize_patch_ops(auto_proposal)
    evidence = _build_evidence(auto_proposal)

    artifact_payload = {
        "proposal_id": proposal_id,
        "ts_iso": ts_iso,
        "policy_target_version": policy_latest_version,
        "policy_target_sha256": policy_latest_sha256,
        "evidence": evidence,
        "patch_ops": patch_ops,
        "meta": {
            "bridged_from": "approval_queue",
            "auto_proposed_by": "learning_os_v2",
            "channel": auto_proposal.get("channel"),
            "window_days": auto_proposal.get("window_days"),
        },
    }
    artifact_hash = _sha256_json(artifact_payload)

    return {
        "proposal_id": proposal_id,
        "ts_iso": ts_iso,
        "policy_target_version": policy_latest_version,
        "policy_target_sha256": policy_latest_sha256,
        "artifact_hash": artifact_hash,
        "evidence": evidence,
        "patch_ops": patch_ops,
    }


def run(
    *,
    queue_jsonl: str,
    proposals_out_jsonl: str,
    policy_dir: str,
    limit: int,
    require_status: str,
    dry_run: bool,
    allow_duplicates: bool,
    allow_noop_write: bool,
) -> Dict[str, Any]:
    store = PolicyStore(policy_dir)
    latest = store.latest()
    policy_latest_version = int(latest.version)
    policy_latest_sha256 = str(latest.sha256)
    latest_policy_obj = latest.policy

    # read + merge approval queue
    queue_records = _read_jsonl(queue_jsonl)
    merged = _merge_approval_queue_records(queue_records)

    # filter by status
    status = (require_status or "APPROVED").upper()
    items = [x for x in merged.values() if str(x.get("status") or "").upper() == status]

    # newest first
    items.sort(key=lambda x: str(x.get("ts") or ""), reverse=True)
    if limit > 0:
        items = items[:limit]

    existing_ids = _load_existing_proposal_ids(proposals_out_jsonl) if (not allow_duplicates) else set()

    converted: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for it in items:
        auto_prop = it.get("proposal") or {}
        if not isinstance(auto_prop, dict):
            skipped.append({"reason": "invalid_proposal_payload", "approval_id": it.get("approval_id")})
            continue

        # convert first (so we can noop-check even if proposal_id already exists)
        out = _convert_one(
            auto_proposal=auto_prop,
            policy_latest_version=policy_latest_version,
            policy_latest_sha256=policy_latest_sha256,
        )

        # 1) noop detection first
        noop = False
        try:
            vr = dry_run_validate(out, latest_policy_obj)
            noop = (vr.get("before_sha256") == vr.get("after_sha256"))
        except Exception as e:
            # keep going, but record the validation failure
            skipped.append(
                {
                    "reason": "dry_run_validate_failed_but_kept",
                    "error": str(e),
                    "proposal_id": out.get("proposal_id"),
                    "approval_id": it.get("approval_id"),
                }
            )

        if noop and (not allow_noop_write):
            skipped.append(
                {
                    "reason": "noop_on_latest_policy",
                    "proposal_id": out.get("proposal_id"),
                    "approval_id": it.get("approval_id"),
                    "policy_latest": {"version": policy_latest_version, "sha256": policy_latest_sha256},
                }
            )
            continue

        # 2) duplicate check after noop
        pid = out.get("proposal_id")
        if (not allow_duplicates) and pid and pid in existing_ids:
            skipped.append({"reason": "duplicate_proposal_id", "proposal_id": pid, "approval_id": it.get("approval_id")})
            continue

        converted.append(out)

        if not dry_run:
            _append_jsonl(proposals_out_jsonl, out)
            if pid:
                existing_ids.add(pid)

    receipt = {
        "ok": True,
        "ts": _now_iso(),
        "queue_jsonl": queue_jsonl,
        "proposals_out_jsonl": proposals_out_jsonl,
        "policy_latest": {"version": policy_latest_version, "sha256": policy_latest_sha256},
        "filter_status": status,
        "input_queue_records": len(queue_records),
        "merged_items": len(merged),
        "selected_items": len(items),
        "converted_count": len(converted),
        "skipped_count": len(skipped),
        "dry_run": bool(dry_run),
        "allow_noop_write": bool(allow_noop_write),
    }
    return {"receipt": receipt, "converted": converted, "skipped": skipped}


def main() -> None:
    p = argparse.ArgumentParser(description="Bridge APPROVED auto-proposals from approval queue into patch proposals jsonl")
    p.add_argument("--queue", default="logs/approvals/approval_queue.jsonl")
    p.add_argument("--out", default="logs/patch_proposals/proposals.jsonl")
    p.add_argument("--policy-dir", default="data/policies")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--status", default="APPROVED", help="APPROVED|REJECTED|PENDING (default APPROVED)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--allow-duplicates", action="store_true", help="allow writing same proposal_id again (not recommended)")
    # default: noop는 기록하지 않음(권장). 필요하면 이 플래그로 noop도 기록 가능.
    p.add_argument("--allow-noop-write", action="store_true", help="write noop proposals too (not recommended)")
    args = p.parse_args()

    out = run(
        queue_jsonl=str(args.queue),
        proposals_out_jsonl=str(args.out),
        policy_dir=str(args.policy_dir),
        limit=int(args.limit),
        require_status=str(args.status),
        dry_run=bool(args.dry_run),
        allow_duplicates=bool(args.allow_duplicates),
        allow_noop_write=bool(args.allow_noop_write),
    )

    print(json.dumps(out["receipt"], ensure_ascii=False, indent=2, sort_keys=True))

    # operator convenience: small tail previews
    if out["converted"]:
        print("\n=== converted (tail 3) ===")
        print(json.dumps(out["converted"][-3:], ensure_ascii=False, indent=2, sort_keys=True))
    if out["skipped"]:
        print("\n=== skipped (tail 5) ===")
        print(json.dumps(out["skipped"][-5:], ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
