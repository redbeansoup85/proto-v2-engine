from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, Literal


def _parse_z(dt: str) -> datetime:
    return datetime.fromisoformat(dt.replace("Z", "+00:00"))


class ExecutionBlocked(Exception):
    """
    FAIL-CLOSED block (must be catchable).
    Test expects str(e) to include human-readable hint keywords.
    """
    def __init__(self, reason_code: str, reason_detail: Optional[str] = None):
        self.reason_code = reason_code
        self.reason_detail = reason_detail or ""
        super().__init__(self.__str__())

    def __str__(self) -> str:
        # Prefer detail so tests can assert substrings like "evidence"/"expired"/"execution_scope"
        if self.reason_detail:
            return self.reason_detail
        return self.reason_code


@dataclass(frozen=True)
class ExecutionAllowed:
    decision: Literal["ALLOW"] = "ALLOW"


@dataclass(frozen=True)
class ExecutionResultBlocked:
    status: Literal["BLOCKED"] = "BLOCKED"
    reason_code: str = "UNKNOWN"
    reason_detail: str = ""


ExecutionDecision = Union[ExecutionAllowed, ExecutionBlocked]
ExecutionResult = Union[ExecutionResultBlocked]


@dataclass(frozen=True)
class ApprovalArtifact:
    approval_id: str
    decision: str
    approver_id: str
    expires_at_utc: str
    policy_refs: List[str]

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        now_dt = now or datetime.now(timezone.utc)
        exp = _parse_z(self.expires_at_utc)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return exp <= now_dt


@dataclass(frozen=True)
class ExecutionEnvelope:
    """
    Phase-2 execution envelope (tests/phase2 expected kwargs).
    """
    execution_scope: str
    allowed_actions: List[str]
    allowed_venues: List[str]
    max_size: str
    time_limit_utc: str
    idempotency_key: str
    risk_flags: List[str]
