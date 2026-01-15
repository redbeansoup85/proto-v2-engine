# infra/storage/approval_queue_repo.py
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


class FileBackedApprovalQueue:
    """
    JSONL 'approval queue' repo (append-only event log).

    Each line is either:
      1) enqueue record (base)
      2) status update record (event)

    Why append-only:
    - audit-friendly (event sourcing)
    - safer in early alpha (no in-place mutation)
    - preserves history (who changed what, when)

    Record shapes:

    1) ENQUEUE
       {
         "record_type": "APPROVAL_ENQUEUE_V1",
         "approval_id": "...",
         "ts": "...",
         "kind": "POLICY_PATCH_PROPOSAL_REVIEW",
         "proposal_id": "...",
         "org_id": "...",
         "site_id": "...",
         "channel": "...",
         "status": "PENDING",
         "proposal": {...}
       }

    2) UPDATE
       {
         "record_type": "APPROVAL_UPDATE_V1",
         "approval_id": "...",
         "ts": "...",
         "status": "APPROVED" | "REJECTED" | "PENDING",
         "note": "...",
         "reviewer_id": "...",
         "reviewer_role": "...",
         "metadata": {...}
       }

    Read behavior:
    - get_by_id(): returns the latest merged view (enqueue + latest update)
    - list_recent(): returns latest merged views, newest first
    """

    def __init__(self, path: str):
        self.path = path
        _ensure_dir(self.path)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                f.write("")

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    def enqueue(self, proposal: Dict[str, Any]) -> str:
        approval_id = f"appr_{uuid.uuid4().hex}"
        item: Dict[str, Any] = {
            "record_type": "APPROVAL_ENQUEUE_V1",
            "approval_id": approval_id,
            "ts": _now_iso(),
            "kind": "POLICY_PATCH_PROPOSAL_REVIEW",
            "proposal_id": proposal.get("proposal_id"),
            "org_id": proposal.get("org_id"),
            "site_id": proposal.get("site_id"),
            "channel": proposal.get("channel"),
            "status": "PENDING",
            # alpha: embed full proposal artifact for easy review
            "proposal": proposal,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
        return approval_id

    def mark_status(self, approval_id: str, status: str, note: Optional[str] = None) -> None:
        """
        Append a status update event (append-only).
        This does not mutate the original enqueue record.

        Kept for backward compatibility with earlier code.
        """
        status = (status or "").strip().upper()
        if status not in ("PENDING", "APPROVED", "REJECTED"):
            raise ValueError(f"Invalid status: {status}")

        item: Dict[str, Any] = {
            "record_type": "APPROVAL_UPDATE_V1",
            "approval_id": approval_id,
            "ts": _now_iso(),
            "status": status,
            "note": note,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    def update_status(
        self,
        *,
        approval_id: str,
        status: str,
        reviewer_id: str,
        reviewer_role: str = "human",
        notes: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Compatibility method for v2-alpha CLI/jobs.

        Keeps append-only model by writing an APPROVAL_UPDATE_V1 record,
        enriched with reviewer fields.

        Returns:
        - True if the approval_id exists (enqueue exists)
        - False otherwise (still writes event? -> NO; do not write if not found)
        """
        status = (status or "").strip().upper()
        if status not in ("PENDING", "APPROVED", "REJECTED"):
            raise ValueError("status must be one of: PENDING, APPROVED, REJECTED")

        # only allow updates for existing approvals
        base = self.get_by_id(approval_id)
        if base is None:
            return False

        item: Dict[str, Any] = {
            "record_type": "APPROVAL_UPDATE_V1",
            "approval_id": approval_id,
            "ts": _now_iso(),
            "status": status,
            "note": notes,
            "reviewer_id": reviewer_id,
            "reviewer_role": reviewer_role,
            "metadata": metadata or {},
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
        return True

    # ------------------------------------------------------------------
    # Read (raw)
    # ------------------------------------------------------------------
    def _read_all(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        out: List[Dict[str, Any]] = []
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out

    # ------------------------------------------------------------------
    # Read (merged)
    # ------------------------------------------------------------------
    def _merge_latest_views(self) -> Dict[str, Dict[str, Any]]:
        """
        Return {approval_id: merged_view} where merged_view is based on:
        - the enqueue record (must exist)
        - the latest update record (optional)
        """
        records = self._read_all()
        enqueues: Dict[str, Dict[str, Any]] = {}
        latest_update: Dict[str, Dict[str, Any]] = {}

        for r in records:
            rtype = r.get("record_type")
            aid = r.get("approval_id")
            if not aid:
                continue

            if rtype == "APPROVAL_ENQUEUE_V1":
                # keep latest enqueue if duplicates (overwrite is fine)
                enqueues[aid] = r
            elif rtype == "APPROVAL_UPDATE_V1":
                # append-only chronological -> overwrite yields latest
                latest_update[aid] = r

        merged: Dict[str, Dict[str, Any]] = {}
        for aid, base in enqueues.items():
            view = dict(base)
            upd = latest_update.get(aid)
            if upd:
                view["status"] = upd.get("status", view.get("status"))
                view["status_updated_ts"] = upd.get("ts")

                if upd.get("note") is not None:
                    view["status_note"] = upd.get("note")

                # reviewer fields (optional)
                if upd.get("reviewer_id") is not None:
                    view["reviewer_id"] = upd.get("reviewer_id")
                if upd.get("reviewer_role") is not None:
                    view["reviewer_role"] = upd.get("reviewer_role")
                if upd.get("metadata") is not None:
                    view["review_metadata"] = upd.get("metadata")

            merged[aid] = view

        return merged

    def get_by_id(self, approval_id: str) -> Optional[Dict[str, Any]]:
        """
        Returns the latest merged view for a given approval_id.
        """
        merged = self._merge_latest_views()
        return merged.get(approval_id)

    def list_recent(self, limit: int = 50, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Returns latest merged approval items (newest first).
        Optionally filter by status.
        """
        if limit <= 0:
            return []

        merged = self._merge_latest_views()
        items = list(merged.values())

        if status:
            s = status.strip().upper()
            items = [it for it in items if str(it.get("status", "")).upper() == s]

        def _ts(item: Dict[str, Any]) -> str:
            return str(item.get("ts") or "")

        items.sort(key=_ts, reverse=True)
        return items[:limit]
