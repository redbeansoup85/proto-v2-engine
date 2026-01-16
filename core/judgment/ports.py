from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, runtime_checkable

from core.judgment.models import DpaRecord


@runtime_checkable
class DpaRepositoryPort(Protocol):
    def get(self, dpa_id: str) -> Optional[DpaRecord]: ...
    def create(self, dpa: DpaRecord) -> DpaRecord: ...
    def save(self, dpa: DpaRecord) -> DpaRecord: ...


@runtime_checkable
class ApprovalQueuePort(Protocol):
    # enqueue full request (PENDING)
    def enqueue(self, item: Any) -> None: ...

    # append status change (APPROVED/REJECTED)
    def set_status(self, approval_id: str, status: str) -> None: ...

    # reducer-style reads
    def get_latest_by_approval_id(self, approval_id: str): ...
    def get_latest_for_dpa(self, dpa_id: str): ...


@runtime_checkable
class DpaApplyPort(Protocol):
    """
    Engine-side apply port used by constitutional_transition.
    Must exist even in NOOP/fail-closed mode.
    """
    def get_dpa(self, *, dpa_id: str) -> Optional[Dict[str, Any]]: ...
    def apply(self, *, dpa_id: str, selected_option_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]: ...
