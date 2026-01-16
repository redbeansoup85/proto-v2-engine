from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict, Any


@dataclass(frozen=True)
class ApprovalQueueItem:
    approval_id: str
    dpa_id: str
    event_id: str
    status: str          # "PENDING" | "APPROVED" | "REJECTED"
    authority_id: str
    rationale_ref: str
    selected_option_id: str


class FileBackedApprovalQueue:
    """
    Append-only approvals.jsonl (snapshot per mutation)
    - enqueue() writes full snapshot with status=PENDING
    - set_status() appends full snapshot (same ids, updated status)
    - get_latest_by_approval_id() scans and returns last snapshot
    """

    def __init__(self, root_dir: str) -> None:
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "approvals.jsonl"

    def _iter(self):
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                yield json.loads(ln)

    def enqueue(self, item: ApprovalQueueItem) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")

    def get_latest_by_approval_id(self, approval_id: str) -> Optional[ApprovalQueueItem]:
        last: Optional[Dict[str, Any]] = None
        for obj in self._iter():
            if obj.get("approval_id") == approval_id:
                last = obj
        return ApprovalQueueItem(**last) if last else None

    def get_latest_for_dpa(self, dpa_id: str) -> Optional[ApprovalQueueItem]:
        last: Optional[Dict[str, Any]] = None
        for obj in self._iter():
            if obj.get("dpa_id") == dpa_id:
                last = obj
        return ApprovalQueueItem(**last) if last else None

    def set_status(self, approval_id: str, status: str) -> None:
        latest = self.get_latest_by_approval_id(approval_id)
        if latest is None:
            # keep behavior simple for v0.6: append-only store cannot update non-existent item
            raise ValueError(f"approval_id not found: {approval_id}")

        snap = ApprovalQueueItem(
            approval_id=latest.approval_id,
            dpa_id=latest.dpa_id,
            event_id=latest.event_id,
            status=status,
            authority_id=latest.authority_id,
            rationale_ref=latest.rationale_ref,
            selected_option_id=latest.selected_option_id,
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(snap), ensure_ascii=False) + "\n")
