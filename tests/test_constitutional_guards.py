from datetime import datetime
from pathlib import Path
from typing import Optional
import json
import pytest

from core.engine.constitutional_transition import (
    JudgmentApproval,
    constitutional_transition,
)

from core.judgment.models import DpaRecord, HumanDecision, DpaOption
from core.judgment.service import DpaService


# ---- Helpers ----

def _load_demo_payload() -> dict:
    root = Path(__file__).resolve().parents[1]
    p = root / "docs" / "demo" / "v0_3_childcare.json"
    return json.loads(p.read_text(encoding="utf-8"))


# ---- In-memory DPA infra (test-only) ----

class _MemRepo:
    def __init__(self):
        self.db = {}

    def create(self, dpa: DpaRecord) -> DpaRecord:
        self.db[dpa.dpa_id] = dpa
        return dpa

    def get(self, dpa_id: str) -> Optional[DpaRecord]:
        return self.db.get(dpa_id)

    def save(self, dpa: DpaRecord) -> DpaRecord:
        self.db[dpa.dpa_id] = dpa
        return dpa


class _NoopComposer:
    def compose(self, dpa_id: str, event_id: str, context: dict) -> DpaRecord:
        # Not used in these tests, but DpaService requires it.
        return DpaRecord(dpa_id=dpa_id, event_id=event_id, context_json=context)


def _make_service() -> tuple[DpaService, _MemRepo]:
    repo = _MemRepo()
    svc = DpaService(repo=repo, composer=_NoopComposer())
    return svc, repo


def _seed_approved_dpa(svc: DpaService, *, dpa_id: str) -> None:
    # Create an APPROVED DPA with required approval fields and human decision.
    dpa = DpaRecord(
        dpa_id=dpa_id,
        event_id="evt_001",
        options_json=[
            DpaOption(option_id="opt_1", title="Proceed", blocked=False),
        ],
    )
    # Submit human decision via service to respect transition constraints.
    svc.repo.create(dpa)  # create in repo first
    svc.submit_human_decision(
        dpa_id=dpa_id,
        decision=HumanDecision(
            selected_option_id="opt_1",
            reason_codes=["TEST"],
            approver_name="Tester",
            approver_role="Owner",
            signature="Tester@now",
            decided_at=datetime.utcnow(),
        ),
    )


# ---- Fakes ----

class FakeJudgmentPort:
    def __init__(self, approval: Optional[JudgmentApproval]):
        self._approval = approval

    def get_approval(self, *, dpa_id: str) -> JudgmentApproval:
        if self._approval is None:
            raise RuntimeError("JudgmentPort not connected")
        return self._approval

class FakeEmotionPort:
    def read_signal(self, *, subject_id: str, at: datetime):
        return {"mood": "anxious"}


# ---- Tests ----

def test_no_judgment_no_transition():
    svc, _ = _make_service()
    with pytest.raises(PermissionError):
        constitutional_transition(
            dpa_id="dpa_001",
            judgment_port=None,
            dpa_apply_port=svc,
            prelude_output=_load_demo_payload(),
            strict=False,
        )


def test_reject_is_immutable():
    svc, _ = _make_service()
    jp = FakeJudgmentPort(
        JudgmentApproval(
            approval_id="appr_001",
            decision="REJECT",
            authority_id="human_001",
            rationale_ref="ui://decision/123",
            decided_at=datetime.utcnow(),
            immutable=True,
        )
    )
    with pytest.raises(PermissionError):
        constitutional_transition(
            dpa_id="dpa_002",
            judgment_port=jp,
            dpa_apply_port=svc,
            prelude_output=_load_demo_payload(),
            strict=False,
        )


def test_emotion_not_gate_and_apply_required():
    svc, repo = _make_service()

    # Prepare an APPROVED DPA (apply should succeed)
    _seed_approved_dpa(svc, dpa_id="dpa_003")

    jp = FakeJudgmentPort(
        JudgmentApproval(
            approval_id="appr_002",
            decision="APPROVE",
            authority_id="human_001",
            rationale_ref="ui://decision/456",
            decided_at=datetime.utcnow(),
            immutable=True,
        )
    )

    out1 = constitutional_transition(
        dpa_id="dpa_003",
        judgment_port=jp,
        dpa_apply_port=svc,
        prelude_output=_load_demo_payload(),
        strict=False,
        emotion_port=FakeEmotionPort(),
    )
    out2 = constitutional_transition(
        dpa_id="dpa_003",
        judgment_port=jp,
        dpa_apply_port=svc,
        prelude_output=_load_demo_payload(),
        strict=False,
        emotion_port=None,
    )

    # EmotionPort는 gate 조건이 아니므로 둘 다 성공해야 함
    assert out1.meta.org_id == out2.meta.org_id
    assert out1.meta.site_id == out2.meta.site_id

    # ✅ DPA가 실제로 APPLIED 상태로 변경되었는지 확인 (no bypass proof)
    applied = repo.get("dpa_003")
    assert applied is not None
    assert str(applied.status) == "DecisionStatus.APPLIED" or applied.status.name == "APPLIED"


def test_approve_but_not_applied_blocks_execution():
    svc, _ = _make_service()

    # DPA exists but still DPA_CREATED (no human decision) -> apply must fail -> execution blocked
    svc.repo.create(DpaRecord(dpa_id="dpa_004", event_id="evt_004"))

    jp = FakeJudgmentPort(
        JudgmentApproval(
            approval_id="appr_004",
            decision="APPROVE",
            authority_id="human_001",
            rationale_ref="ui://decision/999",
            decided_at=datetime.utcnow(),
            immutable=True,
        )
    )

    with pytest.raises(PermissionError):
        constitutional_transition(
            dpa_id="dpa_004",
            judgment_port=jp,
            dpa_apply_port=svc,
            prelude_output=_load_demo_payload(),
            strict=False,
        )
