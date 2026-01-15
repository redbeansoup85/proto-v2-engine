# jobs/bridge_queue_approvals_to_legacy.py
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir(p: str) -> None:
    os.makedirs(os.path.dirname(p), exist_ok=True)


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


def _merge_queue(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Merge append-only approval queue:
      enqueue: APPPROVAL_ENQUEUE_V1
      update:  APPPROVAL_UPDATE_V1

    Return {approval_id: merged_view}
    """
    enq: Dict[str, Dict[str, Any]] = {}
    upd: Dict[str, Dict[str, Any]] = {}

    for r in records:
        aid = r.get("approval_id")
        if not aid:
            continue

        rtype = r.get("record_type")
        if rtype == "APPROVAL_ENQUEUE_V1":
            enq[aid] = r
        elif rtype == "APPROVAL_UPDATE_V1":
            # last-wins (append-only chronological)
            upd[aid] = r

    merged: Dict[str, Dict[str, Any]] = {}
    for aid, base in enq.items():
        view = dict(base)
        u = upd.get(aid)
        if u:
            view["status"] = u.get("status", view.get("status"))
            view["status_updated_ts"] = u.get("ts")
            if u.get("note") is not None:
                view["status_note"] = u.get("note")
        merged[aid] = view
    return merged


def _load_existing_legacy_approvals(approvals_jsonl: str) -> List[Dict[str, Any]]:
    return _read_jsonl(approvals_jsonl)


def _already_written(
    legacy_rows: List[Dict[str, Any]],
    *,
    proposal_id: str,
    reviewer: str,
    comment_prefix: str,
) -> bool:
    """
    Dedup heuristic:
    if there exists a row with same proposal_id + reviewer and comment startswith comment_prefix, treat as already bridged.
    """
    for r in legacy_rows:
        if r.get("proposal_id") != proposal_id:
            continue
        if r.get("reviewer") != reviewer:
            continue
        c = str(r.get("comment") or "")
        if c.startswith(comment_prefix):
            return True
    return False


def _make_legacy_approval_record(
    *,
    proposal_id: str,
    reviewer: str,
    comment: str,
    status: str = "PENDING",
) -> Dict[str, Any]:
    """
    Matches cli.review_patch status() expectations:
      decision == "approved"
      status in ("PENDING","CONSUMED","APPLIED", ...)
    """
    return {
        "proposal_id": proposal_id,
        "reviewer": reviewer,
        "decision": "approved",
        "status": status,
        "comment": comment,
        "ts_iso": _now_iso(),
    }


def run(
    *,
    queue_jsonl: str,
    approvals_jsonl: str,
    require_status: str,
    reviewer: str,
    limit: int,
    dry_run: bool,
    consume_on_write: bool,
) -> Dict[str, Any]:
    queue_records = _read_jsonl(queue_jsonl)
    merged = _merge_queue(queue_records)

    # select approved
    status = (require_status or "APPROVED").upper()
    items = list(merged.values())
    items = [x for x in items if str(x.get("status") or "").upper() == status]

    # newest first by enqueue ts
    items.sort(key=lambda x: str(x.get("ts") or ""), reverse=True)
    if limit > 0:
        items = items[:limit]

    legacy_rows = _load_existing_legacy_approvals(approvals_jsonl)

    written: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    comment_prefix = "bridge: approve auto proposal"

    for it in items:
        auto_prop = it.get("proposal") or {}
        if not isinstance(auto_prop, dict):
            skipped.append({"reason": "invalid_proposal_payload", "approval_id": it.get("approval_id")})
            continue

        proposal_id = auto_prop.get("proposal_id")
        if not proposal_id:
            skipped.append({"reason": "missing_proposal_id", "approval_id": it.get("approval_id")})
            continue

        # dedup
        if _already_written(legacy_rows, proposal_id=proposal_id, reviewer=reviewer, comment_prefix=comment_prefix):
            skipped.append({"reason": "already_written", "proposal_id": proposal_id, "approval_id": it.get("approval_id")})
            continue

        rec = _make_legacy_approval_record(
            proposal_id=proposal_id,
            reviewer=reviewer,
            comment=f"{comment_prefix}",
            status="PENDING",
        )

        if not dry_run:
            _append_jsonl(approvals_jsonl, rec)
            legacy_rows.append(rec)

            if consume_on_write:
                # optional: immediately mark as consumed (some ops styles prefer apply to consume)
                rec2 = dict(rec)
                rec2["status"] = "CONSUMED"
                rec2["consumed_by"] = "ops"
                rec2["consumed_comment"] = "bridge: consumed after apply"
                rec2["consumed_ts_iso"] = _now_iso()
                _append_jsonl(approvals_jsonl, rec2)
                legacy_rows.append(rec2)

        written.append({"proposal_id": proposal_id, "approval_id": it.get("approval_id")})

    receipt = {
        "ok": True,
        "ts": _now_iso(),
        "queue_jsonl": queue_jsonl,
        "approvals_jsonl": approvals_jsonl,
        "filter_status": status,
        "input_queue_records": len(queue_records),
        "merged_items": len(merged),
        "selected_items": len(items),
        "written": len(written),
        "skipped": len(skipped),
        "reviewer": reviewer,
        "dry_run": bool(dry_run),
        "consume_on_write": bool(consume_on_write),
    }
    return {"receipt": receipt, "written": written, "skipped": skipped}


def main() -> None:
    p = argparse.ArgumentParser(description="Bridge APPROVED approval_queue items into legacy approvals.jsonl")
    p.add_argument("--queue", default="logs/approvals/approval_queue.jsonl")
    p.add_argument("--approvals", default="logs/approvals/approvals.jsonl")
    p.add_argument("--status", default="APPROVED")
    p.add_argument("--reviewer", default="seunghyun")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--consume-on-write", action="store_true")
    args = p.parse_args()

    out = run(
        queue_jsonl=str(args.queue),
        approvals_jsonl=str(args.approvals),
        require_status=str(args.status),
        reviewer=str(args.reviewer),
        limit=int(args.limit),
        dry_run=bool(args.dry_run),
        consume_on_write=bool(args.consume_on_write),
    )
    print(json.dumps(out["receipt"], ensure_ascii=False, indent=2, sort_keys=True))
    if out["written"]:
        print("\n=== written (tail 5) ===")
        print(json.dumps(out["written"][-5:], ensure_ascii=False, indent=2, sort_keys=True))
    if out["skipped"]:
        print("\n=== skipped (tail 10) ===")
        print(json.dumps(out["skipped"][-10:], ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
