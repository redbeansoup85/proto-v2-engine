from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class ApprovalQueueItem:
    approval_id: str
    dpa_id: str
    event_id: str
    status: str          # "PENDING" | "APPROVED" | "REJECTED"
    authority_id: str
    rationale_ref: str
    selected_option_id: str = "opt_approve"


class InMemoryApprovalQueue:
    def __init__(self) -> None:
        self._by_approval: Dict[str, ApprovalQueueItem] = {}
        self._latest_for_dpa: Dict[str, str] = {}

    def enqueue(self, item: ApprovalQueueItem) -> None:
        self._by_approval[item.approval_id] = item
        self._latest_for_dpa[item.dpa_id] = item.approval_id

    def get_latest_for_dpa(self, dpa_id: str) -> Optional[ApprovalQueueItem]:
        aid = self._latest_for_dpa.get(dpa_id)
        return self._by_approval.get(aid) if aid else None

    def get_latest_by_approval_id(self, approval_id: str) -> Optional[ApprovalQueueItem]:
        return self._by_approval.get(approval_id)

    def set_status(self, approval_id: str, status: str) -> None:
        cur = self._by_approval.get(approval_id)
        if cur is None:
            raise ValueError(f"Unknown approval_id: {approval_id}")
        nxt = ApprovalQueueItem(
            approval_id=cur.approval_id,
            dpa_id=cur.dpa_id,
            event_id=cur.event_id,
            status=status,
            selected_option_id=cur.selected_option_id,
        authority_id=cur.authority_id,
            rationale_ref=cur.rationale_ref,
        )
        self.enqueue(nxt)
