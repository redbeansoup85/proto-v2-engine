from datetime import datetime
from pathlib import Path
from typing import Optional
import json
import pytest

from core.engine.constitutional_transition import (
    JudgmentApproval,
    constitutional_transition,
)

# ---- Helpers ----

def _load_demo_payload() -> dict:
    root = Path(__file__).resolve().parents[1]
    p = root / "docs" / "demo" / "v0_3_childcare.json"
    return json.loads(p.read_text(encoding="utf-8"))

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
    with pytest.raises(PermissionError):
        constitutional_transition(
            dpa_id="dpa_001",
            judgment_port=None,
            prelude_output=_load_demo_payload(),
        )

def test_reject_is_immutable():
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
            prelude_output=_load_demo_payload(),
        )

def test_emotion_not_gate():
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
        prelude_output=_load_demo_payload(),
        strict=False,
        emotion_port=FakeEmotionPort(),
    )
    out2 = constitutional_transition(
        dpa_id="dpa_003",
        judgment_port=jp,
        prelude_output=_load_demo_payload(),
        strict=False,
        emotion_port=None,
    )

    # EmotionPort는 eligibility에 영향이 없어야 함 (둘 다 성공)
    assert out1.meta.org_id == out2.meta.org_id
    assert out1.meta.site_id == out2.meta.site_id
