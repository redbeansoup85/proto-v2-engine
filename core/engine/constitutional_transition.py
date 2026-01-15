from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Protocol

from core.engine.run_engine import run_engine


# ---- Ports (Protocol only; implementations live outside the engine) ----

@dataclass(frozen=True)
class JudgmentApproval:
    approval_id: str
    decision: str          # "APPROVE" | "REJECT"
    authority_id: str
    rationale_ref: str
    decided_at: datetime
    immutable: bool


class JudgmentPort(Protocol):
    def get_approval(self, *, dpa_id: str) -> JudgmentApproval: ...


class EmotionPort(Protocol):
    def read_signal(self, *, subject_id: str, at: datetime) -> Optional[dict]: ...


# ---- Constitutional transition entrypoint ----

def constitutional_transition(
    *,
    dpa_id: str,
    judgment_port: Optional[JudgmentPort],
    prelude_output: Any,
    strict: bool = True,
    emotion_port: Optional[EmotionPort] = None,
) -> Any:
    """
    Constitutional Runtime Guard (LOCK semantics):
    - No Judgment -> No Engine Run (fail-closed)
    - Approval must be immutable and have an authority_id
    - REJECT is immutable terminal (no run)
    - EmotionPort is not a gate condition (explicitly ignored for eligibility)
    - On APPROVE -> delegate to real engine run_engine(prelude_output)
    """
    if judgment_port is None:
        raise PermissionError("No JudgmentPort (fail-closed)")

    approval = judgment_port.get_approval(dpa_id=dpa_id)

    if approval.immutable is not True:
        raise PermissionError("Approval must be immutable")

    if not approval.authority_id:
        raise PermissionError("Missing authority_id")

    if approval.decision == "REJECT":
        raise PermissionError("Rejected (immutable)")

    # Emotion is explicitly not a gate condition for eligibility:
    _ = emotion_port

    # ✅ Real engine binding (v0.2):
    return run_engine(prelude_output, strict=strict)
