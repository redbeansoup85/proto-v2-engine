# cli/review_patch.py
from __future__ import annotations

import argparse
import glob
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.policy_store.store import PolicyStore
from core.B_learning.approval import (
    approve_only,
    apply_after_approvals,
    dry_run_validate,
    find_proposal,
)
from core.C_action.plan_from_receipt import plan_pack_queue_bundle_from_receipt

# NEW: approval queue (append-only)
from infra.storage.approval_queue_repo import FileBackedApprovalQueue


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    if not path or not os.path.exists(path):
        return []
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _latest_receipt_for(applied_dir: str, proposal_id: str) -> Optional[Dict[str, Any]]:
    """
    Return parsed latest receipt dict with helper metadata:
      _receipt_path, _receipt_mtime
    """
    if not applied_dir or not os.path.isdir(applied_dir):
        return None

    paths = [
        p
        for p in glob.glob(os.path.join(applied_dir, "receipt_*.json"))
        if proposal_id in os.path.basename(p)
    ]
    if not paths:
        return None

    paths.sort(key=lambda p: os.path.getmtime(p))
    path = paths[-1]
    mtime = os.path.getmtime(path)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["_receipt_path"] = path
        data["_receipt_mtime"] = mtime
        return data
    except Exception:
        return {"_receipt_path": path, "_receipt_mtime": mtime}


def find_latest_receipt_path(applied_dir: str, proposal_id: str) -> str:
    """
    Find the latest receipt file path for a proposal_id under applied_dir.
    """
    rec = _latest_receipt_for(applied_dir, proposal_id)
    if not isinstance(rec, dict) or "_receipt_path" not in rec:
        raise FileNotFoundError(f"No receipt found for proposal_id={proposal_id} in {applied_dir}")
    return str(rec["_receipt_path"])


# =============================================================================
# Existing (policy patch governance) commands
# =============================================================================

def cmd_show(args: argparse.Namespace) -> None:
    proposal = find_proposal(args.proposals, args.proposal_id)

    store = PolicyStore(args.policy_dir)
    latest = store.latest()
    result = dry_run_validate(proposal, latest.policy)

    print("=== PROPOSAL SUMMARY ===")
    print(f"proposal_id: {proposal.get('proposal_id')}")
    print(f"ts_iso:      {proposal.get('ts_iso')}")
    print(f"target_ver:  {proposal.get('policy_target_version')}")
    print(f"target_hash: {proposal.get('policy_target_sha256')}")
    print(f"artifact:    {proposal.get('artifact_hash')}")
    print()
    print("=== EVIDENCE ===")
    print(json.dumps(proposal.get("evidence"), ensure_ascii=False, indent=2, sort_keys=True))
    print()
    print("=== PATCH OPS ===")
    print(json.dumps(proposal.get("patch_ops"), ensure_ascii=False, indent=2, sort_keys=True))
    print()
    print("=== DIFF (latest -> patched) ===")
    print(
        json.dumps(
            {
                "warnings": result["warnings"],
                "before_sha256": result["before_sha256"],
                "after_sha256": result["after_sha256"],
                "latest_version": latest.version,
                "latest_sha256": latest.sha256,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


def cmd_dry_run(args: argparse.Namespace) -> None:
    proposal = find_proposal(args.proposals, args.proposal_id)
    store = PolicyStore(args.policy_dir)
    latest = store.latest()
    result = dry_run_validate(proposal, latest.policy)
    out = {
        "proposal_id": proposal.get("proposal_id"),
        "latest_version": latest.version,
        "latest_sha256": latest.sha256,
        "warnings": result["warnings"],
        "before_sha256": result["before_sha256"],
        "after_sha256": result["after_sha256"],
        "noop": (result["before_sha256"] == result["after_sha256"]),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))


def cmd_approve(args: argparse.Namespace) -> None:
    # NOTE: this is your existing approval mechanism (NOT the new approval queue)
    rec = approve_only(
        approvals_jsonl=args.approvals,
        proposals_jsonl=args.proposals,
        proposal_id=args.proposal_id,
        reviewer=args.reviewer,
        comment=args.comment,
    )
    print(json.dumps(rec.__dict__, ensure_ascii=False, indent=2, sort_keys=True))


def cmd_apply(args: argparse.Namespace) -> None:
    rec = apply_after_approvals(
        approvals_jsonl=args.approvals,
        proposals_jsonl=args.proposals,
        applied_receipts_dir=args.applied_dir,
        policy_dir=args.policy_dir,
        proposal_id=args.proposal_id,
        applier=args.applier,
        comment=args.comment,
        min_approvals=args.min_approvals,
        strategy=args.strategy,
    )
    print(json.dumps(rec.__dict__, ensure_ascii=False, indent=2, sort_keys=True))


def _dedupe_latest_per_reviewer(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    approvals.jsonl is append-only, so multiple records can exist for the same
    (proposal_id, reviewer). Keep only the latest by ts_iso.

    This fixes the common “PENDING remains after CONSUMED/APPLIED” symptom,
    by collapsing reviewer state to the latest event.
    """
    latest: Dict[Tuple[str, str], Dict[str, Any]] = {}
    rows_sorted = sorted(rows, key=lambda r: str(r.get("ts_iso") or ""))
    for r in rows_sorted:
        pid = r.get("proposal_id")
        reviewer = r.get("reviewer")
        if not pid or not reviewer:
            continue
        latest[(pid, reviewer)] = r
    return list(latest.values())


def cmd_status(args: argparse.Namespace) -> None:
    approvals = _read_jsonl(args.approvals)

    def is_approved_pending(r: Dict[str, Any]) -> bool:
        return r.get("decision") == "approved" and r.get("status") == "PENDING"

    def is_consumed(r: Dict[str, Any]) -> bool:
        return r.get("decision") == "approved" and r.get("status") == "CONSUMED"

    def is_applied(r: Dict[str, Any]) -> bool:
        return r.get("status") in ("APPLIED", "APPLIED_NOOP")

    if args.proposal_id:
        pid = args.proposal_id
        rows = [r for r in approvals if r.get("proposal_id") == pid]

        # NEW: merge reviewer state (keep latest per reviewer for this proposal)
        rows = _dedupe_latest_per_reviewer(rows)

        pending = [r for r in rows if is_approved_pending(r)]
        consumed = [r for r in rows if is_consumed(r)]
        applied = [r for r in rows if is_applied(r)]

        pending_approvers = sorted({r.get("reviewer") for r in pending if r.get("reviewer")})
        consumed_approvers = sorted({r.get("reviewer") for r in consumed if r.get("reviewer")})

        applied_sorted = sorted(applied, key=lambda r: r.get("ts_iso") or "")
        last_applied = applied_sorted[-1] if applied_sorted else None

        proposal_found = True
        try:
            _ = find_proposal(args.proposals, pid)
        except Exception:
            proposal_found = False

        latest_policy = None
        try:
            store = PolicyStore(args.policy_dir)
            snap = store.latest()
            latest_policy = {"version": snap.version, "sha256": snap.sha256}
        except Exception:
            latest_policy = None

        latest_receipt = _latest_receipt_for(args.applied_dir, pid)
        warnings: List[str] = []
        if isinstance(latest_receipt, dict):
            w = latest_receipt.get("warnings")
            if isinstance(w, list):
                warnings = [str(x) for x in w]

        out = {
            "proposal_id": pid,
            "policy_latest": latest_policy,
            "proposal_found": proposal_found,
            "warnings": {"count": len(warnings), "tail": warnings[-5:] if warnings else []},
            "pending_approvals": {
                "count": len(pending),
                "approvers": pending_approvers,
                "records_tail": pending[-min(5, len(pending)):] if pending else [],
            },
            "consumed_approvals": {
                "count": len(consumed),
                "approvers": consumed_approvers,
                "records_tail": consumed[-min(5, len(consumed)):] if consumed else [],
            },
            "applied_records": {"count": len(applied), "last": last_applied},
            "latest_receipt": latest_receipt,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
        return

    # summary mode
    by_pid: Dict[str, List[Dict[str, Any]]] = {}
    for r in approvals:
        pid = r.get("proposal_id")
        if not pid:
            continue
        by_pid.setdefault(pid, []).append(r)

    items: List[Dict[str, Any]] = []
    for pid, rows in by_pid.items():
        # NEW: merge reviewer state per proposal_id
        rows = _dedupe_latest_per_reviewer(rows)

        pending = [r for r in rows if is_approved_pending(r)]
        applied = [r for r in rows if is_applied(r)]
        last_applied = sorted(applied, key=lambda r: r.get("ts_iso") or "")[-1] if applied else None

        latest_receipt = _latest_receipt_for(args.applied_dir, pid)
        warning_count = 0
        if isinstance(latest_receipt, dict) and isinstance(latest_receipt.get("warnings"), list):
            warning_count = len(latest_receipt["warnings"])

        items.append(
            {
                "proposal_id": pid,
                "pending_count": len(pending),
                "pending_approvers": sorted({r.get("reviewer") for r in pending if r.get("reviewer")}),
                "applied_last_status": last_applied.get("status") if last_applied else None,
                "applied_last_ts": last_applied.get("ts_iso") if last_applied else None,
                "warning_count": warning_count,
            }
        )

    items.sort(key=lambda x: (x["pending_count"], x["warning_count"], x["applied_last_ts"] or ""), reverse=True)
    print(json.dumps({"count": len(items), "items": items[: args.limit]}, ensure_ascii=False, indent=2, sort_keys=True))


def cmd_deliver(args: argparse.Namespace) -> None:
    """
    Build delivery artifacts from latest receipt for a proposal_id:
      receipt -> plan -> pack -> queue -> bundles
    """
    proposal_id = args.proposal_id
    receipt_path = find_latest_receipt_path(args.applied_dir, proposal_id)

    plan, plan_path, pack_path, queue_path, bundle_paths = plan_pack_queue_bundle_from_receipt(
        receipt_path=receipt_path,
        plans_dir=args.out_dir,
        index_path=args.index_path,
        packs_dir=args.pack_dir,
        queue_base_dir=args.queue_dir,
        bundle_base_dir=args.bundle_dir,
    )

    out = {
        "proposal_id": proposal_id,
        "receipt": receipt_path,
        "plan": plan_path,
        "pack": pack_path,
        "queue": queue_path,
        "bundles": bundle_paths,
        "noop_apply": getattr(plan, "noop_apply", None),
        "warnings": getattr(plan, "warnings", None),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))


# =============================================================================
# NEW: approval queue commands (append-only event-sourced)
# - This is intentionally separate from the existing approvals_jsonl pipeline.
# - Default path is different to avoid schema collisions.
# =============================================================================

def cmd_queue_list(args: argparse.Namespace) -> None:
    """
    List merged approval queue items.

    IMPORTANT: keep this tolerant to repo API differences:
      - Some repos implement list_recent(limit=...)
      - Some implement list_recent(limit=..., status=...) (we do NOT rely on this)
    """
    q = FileBackedApprovalQueue(path=args.queue)
    items = q.list_recent(limit=args.limit)

    if args.status:
        want = str(args.status).upper()
        items = [x for x in items if str(x.get("status") or "").upper() == want]

    print(json.dumps({"count": len(items), "items": items}, ensure_ascii=False, indent=2, sort_keys=True))


def cmd_queue_show(args: argparse.Namespace) -> None:
    q = FileBackedApprovalQueue(path=args.queue)
    item = q.get_by_id(args.approval_id)
    if item is None:
        raise SystemExit(f"approval_id not found: {args.approval_id}")
    print(json.dumps(item, ensure_ascii=False, indent=2, sort_keys=True))


def _normalize_decision(decision: str) -> str:
    d = (decision or "").strip().lower()
    if d in ("approve", "approved", "a", "yes", "y"):
        return "APPROVED"
    if d in ("reject", "rejected", "r", "no", "n"):
        return "REJECTED"
    if d in ("pending", "p"):
        return "PENDING"
    raise ValueError("decision must be: approve | reject | pending")


def cmd_queue_decide(args: argparse.Namespace) -> None:
    """
    Append an approval decision event for approval_id.

    IMPORTANT: we use mark_status(...) because you already validated it exists.
    We do not assume update_status(...) exists.
    """
    q = FileBackedApprovalQueue(path=args.queue)
    status = _normalize_decision(args.decision)

    before = q.get_by_id(args.approval_id)
    if before is None:
        raise SystemExit(f"approval_id not found: {args.approval_id}")

    # use proven API
    q.mark_status(args.approval_id, status, args.note or "")

    after = q.get_by_id(args.approval_id)

    out = {
        "ok": True,
        "approval_id": args.approval_id,
        "decision": status,
        "before_status": (before or {}).get("status"),
        "after_status": (after or {}).get("status"),
        "proposal_id": (after or {}).get("proposal_id"),
        "channel": (after or {}).get("channel"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))


# =============================================================================

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="review_patch")
    sub = p.add_subparsers(dest="cmd", required=True)

    # existing defaults (policy patch pipeline)
    p.add_argument("--policy-dir", default="data/policies")
    p.add_argument("--proposals", default="logs/patch_proposals/proposals.jsonl")
    p.add_argument("--approvals", default="logs/approvals/approvals.jsonl")
    p.add_argument("--applied-dir", default="logs/applied")

    # NEW: approval queue file (separate to avoid schema collision)
    p.add_argument("--queue", default="logs/approvals/approval_queue.jsonl", help="approval queue jsonl (append-only)")

    s = sub.add_parser("show")
    s.add_argument("--proposal-id", required=True)
    s.set_defaults(func=cmd_show)

    d = sub.add_parser("dry-run")
    d.add_argument("--proposal-id", required=True)
    d.set_defaults(func=cmd_dry_run)

    a = sub.add_parser("approve")
    a.add_argument("--proposal-id", required=True)
    a.add_argument("--reviewer", required=True)
    a.add_argument("--comment", default="")
    a.set_defaults(func=cmd_approve)

    ap = sub.add_parser("apply")
    ap.add_argument("--proposal-id", required=True)
    ap.add_argument("--applier", required=True)
    ap.add_argument("--min-approvals", type=int, default=1)
    ap.add_argument("--strategy", choices=["reject", "force", "rebase"], default="reject")
    ap.add_argument("--comment", default="")
    ap.set_defaults(func=cmd_apply)

    st = sub.add_parser("status")
    st.add_argument("--proposal-id", default=None)
    st.add_argument("--limit", type=int, default=50, help="when proposal-id is omitted, show top N")
    st.set_defaults(func=cmd_status)

    dl = sub.add_parser("deliver")
    dl.add_argument("--proposal-id", required=True)
    dl.add_argument("--out-dir", default="logs/delivery_plans")
    dl.add_argument("--index-path", default="logs/delivery_plans/index.jsonl")
    dl.add_argument("--pack-dir", default="logs/delivery_packs")
    dl.add_argument("--queue-dir", default="logs/queues")
    dl.add_argument("--bundle-dir", default="logs/bundles")
    dl.set_defaults(func=cmd_deliver)

    # -----------------------
    # NEW: approval queue cmds
    # -----------------------
    ql = sub.add_parser("queue-list", help="list merged approval queue items (append-only source)")
    ql.add_argument("--limit", type=int, default=50)
    ql.add_argument("--status", default=None, help="PENDING|APPROVED|REJECTED")
    ql.set_defaults(func=cmd_queue_list)

    qs = sub.add_parser("queue-show", help="show one approval queue merged item by approval_id")
    qs.add_argument("--approval-id", required=True)
    qs.set_defaults(func=cmd_queue_show)

    qd = sub.add_parser("queue-decide", help="append an approval decision event for approval_id")
    qd.add_argument("--approval-id", required=True)
    qd.add_argument("--decision", required=True, help="approve|reject|pending")
    qd.add_argument("--reviewer-id", required=True)  # kept for CLI compatibility (not used by mark_status)
    qd.add_argument("--reviewer-role", default="human")  # kept for CLI compatibility
    qd.add_argument("--note", default="")
    qd.set_defaults(func=cmd_queue_decide)

    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
