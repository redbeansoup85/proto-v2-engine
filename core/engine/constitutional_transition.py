from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Protocol

from core.engine.run_engine import run_engine
from core.contracts.execution_envelope import ExecutionEnvelope
from core.contracts.actions import ExecutionAction
from core.execution.executor import run_execution, ExecutionContext
from core.judgment.errors import PolicyError


from core.judgment.ports import DpaApplyPort
# ---- Ports (Protocol only; implementations live outside the engine) ----

@dataclass(frozen=True)
class JudgmentApproval:
    approval_id: str
    decision: str          # "APPROVE" | "REJECT"
    selected_option_id: str
    authority_id: str
    rationale_ref: str
    decided_at: datetime
    immutable: bool


class JudgmentPort(Protocol):
    def get_approval(self, *, dpa_id: str) -> JudgmentApproval: ...


class EmotionPort(Protocol):
    def read_signal(self, *, subject_id: str, at: datetime) -> Optional[dict]: ...



def _is_applied_status(dpa: Any) -> bool:
    """
    Idempotency helper:
    - If status is already APPLIED (terminal), do not re-apply.
    - Works without importing judgment enums (decoupling).
    """
    try:
        st = getattr(dpa, "status", None)
        if st is None:
            return False
        # status may be Enum, string, or object
        name = getattr(st, "name", "")
        s = f"{st} {name}".upper()
        return "APPLIED" in s
    except Exception:
        return False


def constitutional_transition(
    *,
    dpa_id: str,
    judgment_port: Optional[JudgmentPort],
    prelude_output: Any,
    strict: bool = True,
    emotion_port: Optional[EmotionPort] = None,
    dpa_apply_port: Optional[DpaApplyPort] = None,
    execution_envelope: Optional[ExecutionEnvelope] = None,
) -> Any:
    """
    v0.3 LOCK semantics:
    - No Judgment -> No Engine Run (fail-closed)
    - Approval must be immutable and have an authority_id
    - REJECT is immutable terminal (no run)
    - EmotionPort is not a gate condition (explicitly ignored for eligibility)
    - ✅ Engine run is allowed only AFTER DPA apply gate succeeds (no bypass)
      - APPLIED is treated as idempotent success (do not re-apply)
    """
    # (1) Fail-closed without Judgment
    if judgment_port is None:
        raise PermissionError("No JudgmentPort (fail-closed)")

    approval = judgment_port.get_approval(dpa_id=dpa_id)

    amendment_class = _get_amendment_class()
    _enforce_amajor_requires_rationale(amendment_class, approval)


    if not getattr(approval, "selected_option_id", None):
        raise PermissionError("Missing selected_option_id")

    # (2) Approval invariants
    if approval.immutable is not True:
        raise PermissionError("Approval must be immutable")
    if not approval.authority_id:
        raise PermissionError("Missing authority_id")

    # (3) REJECT is immutable terminal
    if approval.decision == "REJECT":
        raise PermissionError("Rejected (immutable)")

    # (4) Emotion is explicitly not a gate condition
    _ = emotion_port

    # (5) ✅ DPA apply gate (no bypass)
    if dpa_apply_port is None:
        raise PermissionError("No DPA apply port (fail-closed)")

    if execution_envelope is None:
        raise PermissionError("No ExecutionEnvelope (fail-closed)")

    try:
        dpa = dpa_apply_port.get_dpa(dpa_id=dpa_id)
        if not _is_applied_status(dpa):
            run_execution(
                envelope=execution_envelope,
                port=dpa_apply_port,
                ctx=ExecutionContext(
                    action=ExecutionAction.apply,
                    confidence=1.0,
                    input_sources=["judgment:approval_queue"],
                    dpa_id=dpa_id,
                    selected_option_id=approval.selected_option_id,
                    context=None,
                ),
            )
    except PolicyError as e:
        # Preserve policy error details for API/debug visibility
        code = getattr(e, "code", "POLICY_ERROR")
        msg = getattr(e, "message", str(e))
        extra = getattr(e, "extra", None)
        raise PermissionError(f"DPA apply blocked: {code}: {msg} | extra={extra}") from e
    except Exception as e:
        raise PermissionError(f"DPA apply blocked: {type(e).__name__}: {e}") from e

    # (6) Real engine binding
    return run_engine(prelude_output, strict=strict)


def _get_amendment_class() -> str:
    import os
    return (os.getenv("META_AMENDMENT_CLASS") or "").strip()


def _enforce_amajor_requires_rationale(amendment_class: str, approval: Any) -> None:
    if amendment_class != "A-MAJOR":
        return
    # A-MAJOR: rationale_ref must exist for auditability.
    rr = getattr(approval, "rationale_ref", None)
    if not rr:
        raise PermissionError("A-MAJOR amendment requires rationale_ref (fail-closed).")
