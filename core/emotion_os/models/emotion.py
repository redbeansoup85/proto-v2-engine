from typing import Optional
from pydantic import BaseModel, Field


class EmotionSelfReport(BaseModel):
    """사용자가 직접 입력한 감정/상태 슬라이더 값"""

    mood: float = Field(..., description="현재 기분 (valence) [-1.0, 1.0]")
    calm: float = Field(..., description="긴장/안정 정도 [-1.0, 1.0]")
    energy: float = Field(..., description="에너지/각성도 [-1.0, 1.0]")
    focus: float = Field(..., description="집중도 [-1.0, 1.0]")


class EmotionContext(BaseModel):
    """해당 감정이 기록된 Scene/상황 정보"""

    location: Optional[str] = Field(
        None, description="장소 (예: home, cafe_kisetsu, office 등)"
    )
    scene: Optional[str] = Field(
        None, description="Scene 이름 (예: evening_focus, weekend_reset 등)"
    )
    purpose: Optional[str] = Field(
        None, description="현재 활동 목적 (deep_work / relax / social 등)"
    )
    with_whom: Optional[str] = Field(
        None, description="혼자인지, 다른 사람과 함께인지 (alone / partner / team 등)"
    )
    note: Optional[str] = Field(
        None, description="자유롭게 남기는 메모"
    )


class EmotionVector(BaseModel):
    """Emotion OS 내부에서 사용하는 4축 감정 벡터"""

    valence: float        # 긍/부정
    arousal: float        # 각성도
    safety: float         # 심리적 안정감
    connection: float     # 연결감 (사람/공간/자기 자신과의 연결)


class EmotionRecordRequest(BaseModel):
    """Emotion OS 엔진에 들어가는 입력 전체 구조"""

    self_report: EmotionSelfReport
    context: Optional[EmotionContext] = None
    previous_emotion: Optional[EmotionVector] = Field(
        None,
        description="직전 기록의 EmotionVector (있으면 drift 계산에 사용)",
    )


class EmotionRecordResponse(BaseModel):
    """Emotion OS 엔진에서 반환하는 결과"""

    emotion_vector: EmotionVector
    primary_emotion: str
    stability_index: float
    confidence_score: float
    scene_fit_score: float
    drift: EmotionVector
