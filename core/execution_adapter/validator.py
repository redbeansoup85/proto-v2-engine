from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Sequence

from .contract import (
    ApprovalArtifact,
    ExecutionRequestArtifact,
    ExecutionAllowed,
    ExecutionBlocked,
    ExecutionDecision,
)


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def validate_execution_preconditions(
    *,
    execution_request: Dict[str, Any] | ExecutionRequestArtifact,
    approval: Dict[str, Any] | ApprovalArtifact | None,
    now_utc: datetime,
    required_capability: str,
) -> ExecutionDecision:
    # FAIL-CLOSED: approval required
    if approval is None:
        return ExecutionBlocked("MISSING_APPROVAL", "no approval record present")

    expires_at = _get(approval, "expires_at")
    if expires_at is None:
        return ExecutionBlocked("INVALID_APPROVAL", "approval missing expires_at")
    if not isinstance(expires_at, datetime):
        return ExecutionBlocked("INVALID_APPROVAL", "expires_at must be datetime")
    if expires_at < now_utc:
        return ExecutionBlocked("APPROVAL_EXPIRED", "approval expired")

    caps: Sequence[str] = _get(approval, "capabilities", []) or []
    if required_capability not in caps:
        return ExecutionBlocked(
            "CAPABILITY_MISSING",
            f"required capability '{required_capability}' not granted",
        )

    evidence = _get(execution_request, "evidence")
    if not evidence:
        return ExecutionBlocked("MISSING_EVIDENCE", "execution evidence required")

    return ExecutionAllowed()
