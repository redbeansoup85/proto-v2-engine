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

# ---- DEV in-memory wiring (v0.5 LOCK 기준선) ----
_REPO = InMemoryDpaRepository()


class _MinimalComposer:
    """
    v0.5: constitutional E2E를 위해 필요한 최소 Composer.
    도메인별 Composer는 이후 플러그인으로 교체.
    """
    def compose(self, *, dpa_id: str, event_id: str, context: Dict[str, Any]) -> DpaRecord:
        # 최소 1개 옵션을 제공해야 HumanDecision이 선택 가능
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
    # prelude_output은 run_engine adapter가 기대하는 JSON 포맷이어야 함
    prelude_output: Dict[str, Any]

    approval: ApprovalPayload = Field(default_factory=ApprovalPayload)

    # DPA state machine을 실제로 통과시키기 위한 인간 결정(서명 포함)
    human_decision: Optional[HumanDecision] = None


class SeedReq(BaseModel):
    dpa_id: str = "dpa_demo_001"
    event_id: str = "evt_demo_001"
    selected_option_id: str = "opt_approve"



import os

if os.getenv("METAOS_DEV", "0") == "1":
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
        _SVC.create_dpa(
            event_id=req.event_id,
            context={"source": "constitutional_api"},
            dpa_id=req.dpa_id,
        )


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
    # 1) DPA 준비 (없으면 생성)
    dpa = _SVC.repo.get(req.dpa_id)
    if dpa is None:
        _SVC.create_dpa(
            event_id=req.event_id,
            context={"source": "constitutional_api"},
            dpa_id=req.dpa_id,
        )

    # 2) 승인 payload가 REJECT면, DPA는 굳이 apply까지 갈 필요 없음 (헌법이 fail-closed로 막아야 함)
    # 하지만 "apply gate"가 존재해야 하므로, APPROVE일 때만 DPA를 승인+apply로 진입시킴.
    if req.approval.decision == "APPROVE":
        # human_decision이 없으면 최소값으로 채움 (v0.5 dev convenience)
        if req.human_decision is None:
            raise HTTPException(status_code=403, detail="Missing human_decision (no bypass)")
            req.human_decision = HumanDecision(
                selected_option_id="opt_approve",
                reason_codes=["DEV_DEFAULT"],
                reason_note="dev default decision",
                approver_name="Tester",
                approver_role="Owner",
                signature="Tester/Owner",
            )

        try:
            _SVC.submit_human_decision(dpa_id=req.dpa_id, decision=req.human_decision)
        except Exception:
            # 이미 승인된 경우 등은 그대로 진행
            pass

        try:
            _SVC.apply(dpa_id=req.dpa_id)
        except Exception:
            # 이미 APPLIED(terminal)면 idempotent로 허용
            pass

    # 3) JudgmentPort: request approval을 그대로 제공하는 최소 포트
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

    # 4) 헌법 전이 실행 (DPA apply gate + run_engine)
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
        print("[constitutional] PermissionError:", str(e))
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
