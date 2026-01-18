from __future__ import annotations
from uuid import uuid4
from core.engine.transition_facade import TransitionDeps, run_transition
from infra.api.audit_sink import audit_envelope_event
from core.contracts.execution_envelope import ExecutionEnvelope
from core.judgment.adapters.judgment_from_queue import ApprovalQueueJudgmentPort

_REPO = None
_SVC = None

from datetime import datetime
from typing import Any, Dict, Optional, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.engine.transition_facade import TransitionDeps, run_transition
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


_REPO = None
_SVC = None
# type: ignore[arg-type]


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
    if _get_service().repo.get(req.dpa_id) is None:
        _get_service().create_dpa(event_id=req.event_id, context={"source": "constitutional_api"}, dpa_id=req.dpa_id)

    # =========================================================
    # (C) If APPROVE, drive DPA to APPROVED and APPLY (best-effort)
    # =========================================================
    if req.approval.decision == "APPROVE":
        try:
            _get_service().start_review(dpa_id=req.dpa_id, reviewer=req.approval.authority_id)
        except Exception:
            pass

        try:
            _get_service().submit_human_decision(dpa_id=req.dpa_id, decision=req.human_decision)  # type: ignore[arg-type]
        except Exception:
            pass

        try:
            _get_service().apply(dpa_id=req.dpa_id)
        except Exception:
            pass
    # =========================================================
    # =========================================================


    # (E) Engine call (v0.8 boundary: router -> facade)
    # =========================================================
    raw_judgment = ApprovalQueueJudgmentPort(approval_queue=_QUEUE)  # type: ignore

    class _CachedJudgmentPort:
        def __init__(self, *, dpa_id: str, approval_obj: object):
            self._dpa_id = dpa_id
            self._approval = approval_obj

        def get_approval(self, *, dpa_id: str):
            if dpa_id != self._dpa_id:
                raise PermissionError("Approval cache mismatch (fail-closed)")
            return self._approval

    try:
        approval = raw_judgment.get_approval(dpa_id=req.dpa_id)
        cached_judgment = _CachedJudgmentPort(
            dpa_id=req.dpa_id,
            approval_obj=approval,
        )

        deps = TransitionDeps(
            approval_queue=_QUEUE,
            judgment_port=cached_judgment,
            dpa_apply_port=NoopDpaApplyPort(),
        )

        envelope = _build_execution_envelope(
            approver_id=approval.authority_id,
            approval_ref=approval.approval_id,
        )

        try:
            audit_envelope_event(
                event="mint",
                dpa_id=req.dpa_id,
                approval_id=approval.approval_id,
                authority_id=approval.authority_id,
                envelope_meta=envelope.meta if hasattr(envelope, "meta") else {},
                outcome="allow",
            )
        except Exception:
            pass

        out = run_transition(
            execution_envelope=envelope,
            deps=deps,
            dpa_id=req.dpa_id,
            prelude_output=req.prelude_output,
        )

        try:
            audit_envelope_event(
                event="enforce",
                dpa_id=req.dpa_id,
                approval_id=approval.approval_id,
                authority_id=approval.authority_id,
                envelope_meta=envelope.meta if hasattr(envelope, "meta") else {},
                outcome="allow",
            )
        except Exception:
            pass

    except PermissionError as e:
        try:
            audit_envelope_event(
                event="enforce",
                dpa_id=req.dpa_id,
                approval_id=approval.approval_id if "approval" in locals() else "n/a",
                authority_id=approval.authority_id if "approval" in locals() else "n/a",
                envelope_meta=envelope.meta if "envelope" in locals() and hasattr(envelope, "meta") else {},
                outcome="deny",
                reason=str(e),
            )
        except Exception:
            pass
        raise HTTPException(status_code=403, detail=str(e))

    return {"ok": True, "engine_output": out}

def _build_execution_envelope(*, approver_id: str, approval_ref: str) -> ExecutionEnvelope:
    """
    API boundary issuance: ExecutionEnvelope must be minted at the boundary (infra/api), never inside core.
    Fail-closed defaults.
    """
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    payload = {
        "meta": {
            "contract_id": f"exec_env__{approval_ref}",
            "envelope_id": f"env__{approval_ref}__{uuid4()}",
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=10)).isoformat(),
            "issuer": "infra.api.routes.constitutional",
            "version": "1.0.0",
        },
        "authority": {
            "domain": "constitutional_transition",
            "allowed_actions": ["apply"],
            "forbidden_actions": ["execute_trade", "webhook", "notify", "publish", "emit"],
            "confidence_floor": 0.0,
        },
        "constraints": {
            "latency_budget_ms": 2000,
            "resource_ceiling": {"cpu_pct": 90.0, "mem_mb": 1024},
            "data_scope": {
                "allowed_sources": ["judgment:approval_queue"],
                "forbidden_sources": ["net:public_web"],
            },
        },
        "audit": {"trace_level": "standard", "retention_policy": "append_only"},
        "human_approval": {"approver_id": approver_id, "approval_ref": approval_ref},
    }
    return ExecutionEnvelope.model_validate(payload)
