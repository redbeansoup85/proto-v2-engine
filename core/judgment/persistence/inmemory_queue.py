from __future__ import annotations

from dataclasses import replace
from typing import Dict, Optional

from core.judgment.persistence.approval_queue import ApprovalQueueItem


class InMemoryApprovalQueue:
    def __init__(self) -> None:
        self._by_id: Dict[str, ApprovalQueueItem] = {}

    def enqueue(self, item: ApprovalQueueItem) -> None:
        self._by_id[item.approval_id] = item

    def set_status(self, approval_id: str, status: str) -> None:
        cur = self._by_id.get(approval_id)
        if cur is None:
            return
        self._by_id[approval_id] = replace(cur, status=status)

    def get_latest_by_approval_id(self, approval_id: str) -> Optional[ApprovalQueueItem]:
        return self._by_id.get(approval_id)

    def get_latest_for_dpa(self, dpa_id: str) -> Optional[ApprovalQueueItem]:
        last = None
        for it in self._by_id.values():
            if it.dpa_id == dpa_id:
                last = it
        return last
