from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.engine.constitutional_transition import constitutional_transition
from core.judgment.models import HumanDecision, DpaRecord, DpaOption
from core.judgment.repo import InMemoryDpaRepository
from core.judgment.persistence.file_repo import FileBackedDpaRepository
from core.judgment.persistence.approval_queue import FileBackedApprovalQueue, ApprovalQueueItem
from core.judgment.persistence.inmemory_queue import InMemoryApprovalQueue
from core.judgment.service import DpaService
from core.judgment.persistence.noop_apply_port import NoopDpaApplyPort


router = APIRouter(prefix="/v1/constitutional", tags=["constitutional"])

# ---- DEV in-memory wiring (v0.5 LOCK baseline) ----
import os

# Storage selection (v0.6): local/dev => file-backed, else in-memory
if os.getenv("METAOS_STORAGE", "memory").lower() == "file":
    _REPO = FileBackedDpaRepository(root_dir=os.getenv("METAOS_DATA_DIR", "var/metaos"))  # type: ignore
else:
    _REPO = InMemoryDpaRepository()

# Approval queue selection (v0.6)
if os.getenv("METAOS_STORAGE", "memory").lower() == "file":
    _QUEUE = FileBackedApprovalQueue(root_dir=os.getenv("METAOS_DATA_DIR", "var/metaos"))  # type: ignore
else:
    _QUEUE = InMemoryApprovalQueue()



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
    approval_id: Optional[str] = None
    dpa_id: str = "dpa_demo_001"
    event_id: str = "evt_demo_001"
    prelude_output: Dict[str, Any]
    approval: ApprovalPayload = Field(default_factory=ApprovalPayload)
    human_decision: Optional[HumanDecision] = None


class SeedReq(BaseModel):
    dpa_id: str = "dpa_demo_001"
    event_id: str = "evt_demo_001"
    selected_option_id: str = "opt_approve"



# ---- v0.6 Approval Queue API ----

class EnqueueApprovalIn(BaseModel):
    approval_id: str
    dpa_id: str
    event_id: str
    selected_option_id: str = "opt_approve"
    authority_id: str = "human_001"
    rationale_ref: str = "ui://constitutional/transition"


@router.post("/approvals/enqueue")
def approvals_enqueue(body: EnqueueApprovalIn) -> Any:
    item = ApprovalQueueItem(
        approval_id=body.approval_id,
        dpa_id=body.dpa_id,
        event_id=body.event_id,
        status="PENDING",
        selected_option_id=body.selected_option_id,
        authority_id=body.authority_id,
        rationale_ref=body.rationale_ref,
    )
    _QUEUE.enqueue(item)  # type: ignore
    return {"ok": True, "approval_id": body.approval_id, "status": "PENDING"}


@router.post("/approvals/{approval_id}/approve")
def approvals_approve(approval_id: str) -> Any:
    _QUEUE.set_status(approval_id, "APPROVED")  # type: ignore
    return {"ok": True, "approval_id": approval_id, "status": "APPROVED"}


@router.post("/approvals/{approval_id}/reject")
def approvals_reject(approval_id: str) -> Any:
    _QUEUE.set_status(approval_id, "REJECTED")  # type: ignore
    return {"ok": True, "approval_id": approval_id, "status": "REJECTED"}



@router.post("/transition")
def transition(req: TransitionRequest) -> Any:
    import os
    env = os.getenv("METAOS_ENV", "dev").lower()

    # =========================================================
    # (A) v0.6 Approval Gate (no-bypass)
    # =========================================================
    if req.approval.decision == "APPROVE":
        if not req.approval_id:
            raise HTTPException(status_code=403, detail="Missing approval_id (no bypass)")

        # NOTE: your queue currently supports get_latest_for_dpa() and/or get_latest_by_approval_id()
        latest = None
        if hasattr(_QUEUE, "get_latest_by_approval_id"):
            latest = _QUEUE.get_latest_by_approval_id(req.approval_id)  # type: ignore
        elif hasattr(_QUEUE, "get_latest_for_dpa"):
            latest = _QUEUE.get_latest_for_dpa(req.dpa_id)  # type: ignore

        if latest is None:
            raise HTTPException(status_code=409, detail={"code": "APPROVAL_NOT_FOUND", "approval_id": req.approval_id})

        if getattr(latest, "status", None) != "APPROVED":
            raise HTTPException(status_code=409, detail={"code": "APPROVAL_NOT_APPROVED", "status": getattr(latest, "status", None)})

        if getattr(latest, "dpa_id", None) != req.dpa_id:
            raise HTTPException(status_code=409, detail={"code": "APPROVAL_MISMATCH_DPA", "approval_dpa_id": getattr(latest, "dpa_id", None), "dpa_id": req.dpa_id})

        if getattr(latest, "event_id", None) != req.event_id:
            raise HTTPException(status_code=409, detail={"code": "APPROVAL_MISMATCH_EVENT", "approval_event_id": getattr(latest, "event_id", None), "event_id": req.event_id})

        # Build HumanDecision from approval queue (source of truth)
        req.human_decision = HumanDecision(
            selected_option_id=getattr(latest, "selected_option_id", "opt_approve"),
            reason_codes=["APPROVAL_QUEUE"],
            reason_note=f"approval_id={getattr(latest, 'approval_id', req.approval_id)}",
            approver_name=getattr(latest, "authority_id", "unknown"),
            approver_role="Approver",
            signature=getattr(latest, "authority_id", "unknown"),
        )

    # =========================================================
    # (B) Ensure DPA exists
    # =========================================================
    if _SVC.repo.get(req.dpa_id) is None:
        _SVC.create_dpa(event_id=req.event_id, context={"source": "constitutional_api"}, dpa_id=req.dpa_id)

    # =========================================================
    # (C) If APPROVE, drive DPA to APPROVED and APPLY (best-effort)
    # =========================================================
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

    # =========================================================
    # (D) JudgmentPort wrapper
    # =========================================================
    class _ApprovalObj:
        def __init__(self, a: ApprovalPayload):
            self.approval_id = req.approval_id or "appr_req"
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

    # =========================================================
    # (E) Engine call (dev/local: debug surfacing)
    # =========================================================
    if env in ("dev", "local"):
        try:
            out = constitutional_transition(
                dpa_id=req.dpa_id,prelude_output=req.prelude_output,
                judgment_port=_JudgmentPort(req.approval),
                dpa_apply_port=(NoopDpaApplyPort(_SVC.repo) if env in ("dev","local") else None),
            )
            return {"ok": True, "engine_output": out}
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            tb = traceback.format_exc().splitlines()[-25:]
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "TRANSITION_ERROR",
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "trace_tail": tb,
                },
            )
    else:
        out = constitutional_transition(
            dpa_id=req.dpa_id,prelude_output=req.prelude_output,
            judgment_port=_JudgmentPort(req.approval),
                dpa_apply_port=(NoopDpaApplyPort(_SVC.repo) if env in ("dev","local") else None),
        )
        return {"ok": True, "engine_output": out}
