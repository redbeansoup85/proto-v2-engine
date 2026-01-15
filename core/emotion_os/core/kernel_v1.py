# proto-v2-engine/emotion_os/core/kernel_v1.py

from math import sqrt
from typing import Optional

from emotion_os.models.emotion import (
    EmotionSelfReport,
    EmotionContext,
    EmotionVector,
    EmotionRecordRequest,
    EmotionRecordResponse,
)

KERNEL_VERSION = "1.0.0"


def _compute_emotion_vector(self_report: EmotionSelfReport) -> EmotionVector:
    """
    v1.0 단순 매핑 (내부도 [-1.0, 1.0] 스케일 유지):

    - valence    = mood
    - arousal    = energy
    - safety     = calm
    - connection = 0.0 (초기에는 비활성화, 나중에 관계/공간/자기 데이터로 채울 수 있음)
    """
    return EmotionVector(
        valence=float(self_report.mood),
        arousal=float(self_report.energy),
        safety=float(self_report.calm),
        connection=0.0,
    )


def _classify_primary_emotion(vec: EmotionVector) -> str:
    """
    [-1.0, 1.0] 스케일용 간단 rule-based 태깅.
    나중에는 테이블/ML 기반으로 교체할 예정.
    """
    v, a, s = vec.valence, vec.arousal, vec.safety

    # 비교적 안정적이고 기분 좋은 상태
    if v >= 0.4 and a <= 0.2 and s >= 0.2:
        return "calm_joy"

    # 기분도 좋고 각성도도 높은 상태
    if v >= 0.4 and a >= 0.4:
        return "excited_joy"

    # 기분이 안 좋고 긴장/각성이 높은 상태
    if v <= -0.3 and a >= 0.3:
        return "anxious_stress"

    # 기분이 안 좋고 에너지도 낮은 상태
    if v <= -0.3 and a <= -0.2:
        return "low_mood"

    # 각성이 높고 안전감이 낮은 상태
    if a >= 0.5 and s <= -0.1:
        return "tense_focus"

    return "mixed_state"


def _normalize_01(x: float) -> float:
    """[-1,1] → [0,1] 변환"""
    return max(0.0, min(1.0, (x + 1.0) / 2.0))


def _compute_stability(vec: EmotionVector) -> float:
    """
    안정감 점수 (0~1):

    - safety가 높을수록 +
    - arousal이 낮을수록 +
    (둘을 0~1로 정규화해서 평균)
    """
    safety_n = _normalize_01(vec.safety)
    arousal_n = _normalize_01(vec.arousal)

    stability = 0.5 * safety_n + 0.5 * (1.0 - arousal_n)
    return max(0.0, min(1.0, stability))


def _compute_confidence(vec: EmotionVector) -> float:
    """
    상태가 '중립(0,0,0)'에서 멀수록 명확하다고 보고 confidence↑.

    거리 = sqrt(v^2 + a^2 + s^2)
    최대거리 = sqrt(3 * 1^2) = sqrt(3)
    """
    distance = sqrt(
        vec.valence ** 2 + vec.arousal ** 2 + vec.safety ** 2
    )
    max_distance = sqrt(3.0)
    score = distance / max_distance if max_distance > 0 else 0.0
    return max(0.0, min(1.0, score))


def _compute_scene_fit(context: Optional[EmotionContext], vec: EmotionVector) -> float:
    """
    v1.0: 아직 Scene 규칙 없으므로 기본값 0.5.
    나중에 scene/purpose 기반 룰 테이블과 연결하면 됨.
    """
    return 0.5


def _compute_drift(
    current: EmotionVector, previous: Optional[EmotionVector]
) -> EmotionVector:
    """
    이전 감정 벡터가 있을 경우 → current - previous
    없으면 0 벡터.
    """
    if previous is None:
        return EmotionVector(valence=0.0, arousal=0.0, safety=0.0, connection=0.0)

    return EmotionVector(
        valence=current.valence - previous.valence,
        arousal=current.arousal - previous.arousal,
        safety=current.safety - previous.safety,
        connection=current.connection - previous.connection,
    )


class EmotionKernelV1:
    """
    Emotion OS L1 Kernel v1.0
    - 도메인 로직만 담당 (FastAPI/DB/오케스트라와 분리)
    """

    version: str = KERNEL_VERSION

    def evaluate(self, req: EmotionRecordRequest) -> EmotionRecordResponse:
        vec = _compute_emotion_vector(req.self_report)
        primary = _classify_primary_emotion(vec)
        stability = _compute_stability(vec)
        confidence = _compute_confidence(vec)
        scene_fit = _compute_scene_fit(req.context, vec)
        drift = _compute_drift(vec, req.previous_emotion)

        return EmotionRecordResponse(
            emotion_vector=vec,
            primary_emotion=primary,
            stability_index=stability,
            confidence_score=confidence,
            scene_fit_score=scene_fit,
            drift=drift,
        )


# 함수형 인터페이스 (간단 호출용)

_kernel_singleton = EmotionKernelV1()


def evaluate_emotion(req: EmotionRecordRequest) -> EmotionRecordResponse:
    return _kernel_singleton.evaluate(req)
