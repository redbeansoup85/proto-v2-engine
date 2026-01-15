from datetime import datetime
import pytest

# ---- Stubs / Fakes (엔진 바깥 구현체를 흉내냄) ----

class FakeJudgmentApproval:
    def __init__(self, decision="APPROVE", immutable=True, authority_id="human_001"):
        self.approval_id = "appr_001"
        self.decision = decision
        self.authority_id = authority_id
        self.rationale_ref = "ui://decision/123"
        self.decided_at = datetime.utcnow()
        self.immutable = immutable

class FakeJudgmentPort:
    def __init__(self, approval=None):
        self._approval = approval

    def get_approval(self, *, dpa_id: str):
        if self._approval is None:
            raise RuntimeError("JudgmentPort not connected")
        return self._approval

class FakeEmotionPort:
    def read_signal(self, *, subject_id: str, at: datetime):
        # Emotion은 있어도/없어도 동일 결과여야 함
        return {"mood": "anxious"}

# ---- 최소 엔진 인터페이스 가정 (실제 엔진에 맞게 import로 교체 가능) ----

class Engine:
    def __init__(self, judgment_port=None, emotion_port=None):
        self.judgment_port = judgment_port
        self.emotion_port = emotion_port

    def transition(self, *, dpa_id: str):
        # 1) JudgmentPort 없으면 전이 불가
        if self.judgment_port is None:
            raise PermissionError("No JudgmentPort")

        approval = self.judgment_port.get_approval(dpa_id=dpa_id)

        # 2) 불변성/책임 검사
        if approval.immutable is not True:
            raise PermissionError("Approval must be immutable")
        if not approval.authority_id:
            raise PermissionError("Missing authority")

        # 3) REJECT는 비가역 종료
        if approval.decision == "REJECT":
            raise PermissionError("Rejected (immutable)")

        # Emotion은 전이 조건이 아님 (참고만)
        return "TRANSITION_OK"

# ---- Tests ----

def test_no_judgment_no_transition():
    engine = Engine(judgment_port=None)
    with pytest.raises(PermissionError):
        engine.transition(dpa_id="dpa_001")

def test_reject_is_immutable():
    jp = FakeJudgmentPort(approval=FakeJudgmentApproval(decision="REJECT"))
    engine = Engine(judgment_port=jp)
    with pytest.raises(PermissionError):
        engine.transition(dpa_id="dpa_002")

def test_emotion_not_gate():
    # Emotion이 있든 없든 동일 결과여야 함
    jp = FakeJudgmentPort(approval=FakeJudgmentApproval(decision="APPROVE"))
    engine_with_emotion = Engine(judgment_port=jp, emotion_port=FakeEmotionPort())
    engine_without_emotion = Engine(judgment_port=jp, emotion_port=None)

    assert engine_with_emotion.transition(dpa_id="dpa_003") == "TRANSITION_OK"
    assert engine_without_emotion.transition(dpa_id="dpa_003") == "TRANSITION_OK"
