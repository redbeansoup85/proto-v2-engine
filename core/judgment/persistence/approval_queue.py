from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional


@dataclass(frozen=True)
class ApprovalQueueItem:
    approval_id: str
    dpa_id: str
    event_id: str
    selected_option_id: str
    status: str          # "PENDING" | "APPROVED" | "REJECTED"
    authority_id: str
    rationale_ref: str


class FileBackedApprovalQueue:
    """
    Append-only approvals.jsonl (event sourcing)
    Records:
      - enqueue: full ApprovalQueueItem (status=PENDING)
      - status update: {"approval_id": "...", "status": "..."}
    Read:
      - reduce all events => latest state per approval_id
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

    def _reduce(self) -> Dict[str, Dict]:
        """
        approval_id -> latest object dict
        Reducer rule:
          - if full item: replace baseline (has dpa_id)
          - if status-only: patch status if baseline exists
        """
        st: Dict[str, Dict] = {}
        for obj in self._iter():
            aid = obj.get("approval_id")
            if not aid:
                continue
            if "dpa_id" in obj:
                # full snapshot
                st[aid] = obj
            else:
                # status event
                if aid in st and "status" in obj:
                    st[aid]["status"] = obj["status"]
        return st

    def enqueue(self, item: ApprovalQueueItem) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")

    def set_status(self, approval_id: str, status: str) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"approval_id": approval_id, "status": status}, ensure_ascii=False) + "\n")

    def get_latest_by_approval_id(self, approval_id: str) -> Optional[ApprovalQueueItem]:
        st = self._reduce()
        obj = st.get(approval_id)
        return ApprovalQueueItem(**obj) if obj else None

    def get_latest_for_dpa(self, dpa_id: str) -> Optional[ApprovalQueueItem]:
        st = self._reduce()
        last = None
        for obj in st.values():
            if obj.get("dpa_id") == dpa_id:
                last = obj
        return ApprovalQueueItem(**last) if last else None
