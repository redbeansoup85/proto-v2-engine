from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from core.engine.constitutional_transition import JudgmentApproval, JudgmentPort
from core.judgment.ports import ApprovalQueuePort


@dataclass(frozen=True)
class ApprovalQueueJudgmentPort(JudgmentPort):
    """
    Adapter: ApprovalQueuePort -> JudgmentPort
    Engine remains unaware of queue/event-sourcing details.
    """
    approval_queue: ApprovalQueuePort

    def get_approval(self, *, dpa_id: str) -> JudgmentApproval:
        it = self.approval_queue.get_latest_for_dpa(dpa_id)
        if it is None:
            raise PermissionError("No approval found for dpa_id (fail-closed)")

        # Map queue status -> engine decision
        st = (it.status or "").upper()
        if st == "APPROVED":
            decision = "APPROVE"
            immutable = True
        elif st == "REJECTED":
            decision = "REJECT"
            immutable = True
        else:
            # PENDING/unknown: keep immutable=False so engine denies
            decision = "REJECT"
            immutable = False

        return JudgmentApproval(
            approval_id=it.approval_id,
            decision=decision,
            authority_id=it.authority_id,
            rationale_ref=it.rationale_ref,
            decided_at=datetime.now(timezone.utc),
            immutable=immutable,
        )
