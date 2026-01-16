from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.engine.constitutional_transition import constitutional_transition
from core.judgment.models import HumanDecision, DpaRecord, DpaOption
from core.judgment.repo import InMemoryDpaRepository
from core.judgment.service import DpaService


router = APIRouter(prefix="/v1/constitutional", tags=["constitutional"])

# ---- DEV in-memory wiring (v0.5 LOCK baseline) ----
_REPO = InMemoryDpaRepository()


class _MinimalComposer:
    """
    v0.5: minimal composer for constitutional E2E.
    Domain-specific composers will replace this later.
    """
    def compose(self, *, dpa_id: str, event_id: str, context: Dict[str, Any]) -> DpaRecord:
        opt = DpaOption(
            option_id="opt_approve",
            title="Approve and proceed",
            summary="Proceed to engine evaluation",
            blocked=False,
            payload={},
        )
        return DpaRecord(
            dpa_id=dpa_id,
            event_id=event_id,
            context_json=context or {},
            options_json=[opt],
        )


_SVC = DpaService(repo=_REPO, composer=_MinimalComposer())  # type: ignore[arg-type]


# ---- Request/Response ----

class ApprovalPayload(BaseModel):
    decision: Literal["APPROVE", "REJECT"] = "APPROVE"
    authority_id: str = "human_001"
    immutable: bool = True
    rationale_ref: str = "ui://constitutional/transition"
    decided_at: datetime = Field(default_factory=datetime.utcnow)


class TransitionRequest(BaseModel):
    dpa_id: str = "dpa_demo_001"
    event_id: str = "evt_demo_001"
    prelude_output: Dict[str, Any]
    approval: ApprovalPayload = Field(default_factory=ApprovalPayload)
    human_decision: Optional[HumanDecision] = None


class SeedReq(BaseModel):
    dpa_id: str = "dpa_demo_001"
    event_id: str = "evt_demo_001"
    selected_option_id: str = "opt_approve"


@router.post("/__debug_seed")
def __debug_seed(req: SeedReq):
    """
    DEV ONLY:
    - create DPA if missing
    - start_review (best-effort)
    - submit_human_decision => APPROVED
    """
    # create if missing
    try:
        _ = _SVC.get_dpa(dpa_id=req.dpa_id)
    except Exception:
        _SVC.create_dpa(event_id=req.event_id, context={"source": "constitutional_api"}, dpa_id=req.dpa_id)

    # move to reviewing (best-effort)
    try:
        _SVC.start_review(dpa_id=req.dpa_id, reviewer="debug")
    except Exception:
        pass

    # approve -> APPROVED
    hd = HumanDecision(
        selected_option_id=req.selected_option_id,
        reason_codes=["DEBUG"],
        reason_note="debug seed",
        approver_name="Tester",
        approver_role="Owner",
        signature="Tester@local",
    )
    dpa = _SVC.submit_human_decision(dpa_id=req.dpa_id, decision=hd)
    return {"ok": True, "status": str(dpa.status)}


@router.post("/transition")
def transition(req: TransitionRequest) -> Any:
    # (A) Fail-closed for APPROVE without human_decision (no bypass)
    if req.approval.decision == "APPROVE" and req.human_decision is None:
        raise HTTPException(status_code=403, detail="Missing human_decision (no bypass)")

    # (B) Ensure DPA exists
    if _SVC.repo.get(req.dpa_id) is None:
        _SVC.create_dpa(event_id=req.event_id, context={"source": "constitutional_api"}, dpa_id=req.dpa_id)

    # (C) If APPROVE, drive DPA to APPROVED (best-effort) and APPLY (best-effort / idempotent)
    if req.approval.decision == "APPROVE":
        try:
            _SVC.start_review(dpa_id=req.dpa_id, reviewer=req.approval.authority_id)
        except Exception:
            pass

        try:
            _SVC.submit_human_decision(dpa_id=req.dpa_id, decision=req.human_decision)  # type: ignore[arg-type]
        except Exception:
            pass

        try:
            _SVC.apply(dpa_id=req.dpa_id)
        except Exception:
            pass

    # (D) Minimal JudgmentPort wrapper from request approval
    class _ApprovalObj:
        def __init__(self, a: ApprovalPayload):
            self.approval_id = "appr_req"
            self.decision = a.decision
            self.authority_id = a.authority_id
            self.rationale_ref = a.rationale_ref
            self.decided_at = a.decided_at
            self.immutable = a.immutable

    class _JudgmentPort:
        def __init__(self, a: ApprovalPayload):
            self._a = a

        def get_approval(self, *, dpa_id: str):
            return _ApprovalObj(self._a)

    jp = _JudgmentPort(req.approval)

    # (E) Execute constitutional transition (DPA apply gate + run_engine)
    try:
        out = constitutional_transition(
            dpa_id=req.dpa_id,
            judgment_port=jp,
            dpa_apply_port=_SVC,
            prelude_output=req.prelude_output,
            strict=True,
            emotion_port=None,
        )
        return {"ok": True, "engine_output": out}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
