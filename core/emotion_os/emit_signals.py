from __future__ import annotations

from typing import Any, Dict, List

from core.contracts import EngineInput, EngineSignal, SignalType, Severity
from core.emotion_os.constants import (
    VALENCE_KEY,
    AROUSAL_KEY,
    DOMINANT_EMOTION_KEY,
    CHILD_NEGATIVE_EMOTION_SCORE_KEY,
    HIGH_NEGATIVE_CHILD_THRESHOLD,
    CRITICAL_NEGATIVE_CHILD_THRESHOLD,
    STRESS_VALENCE_THRESHOLD,
    STRESS_AROUSAL_THRESHOLD,
)


def _safe_float(features: Dict[str, Any], key: str, default: float = 0.0) -> float:
    v = features.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_str(features: Dict[str, Any], key: str, default: str = "unknown") -> str:
    v = features.get(key)
    return str(v) if v is not None else default


def emit_emotion_signals(inp: EngineInput) -> List[EngineSignal]:
    signals: List[EngineSignal] = []

    features: Dict[str, Any] = inp.prelude.features or {}
    confidence = float(inp.prelude.uncertainty.confidence_score)

    valence = _safe_float(features, VALENCE_KEY, default=0.0)
    arousal = _safe_float(features, AROUSAL_KEY, default=0.0)
    dominant_emotion = _safe_str(features, DOMINANT_EMOTION_KEY, default="unknown")
    child_neg_score = _safe_float(features, CHILD_NEGATIVE_EMOTION_SCORE_KEY, default=0.0)

    details_base = {
        "valence": valence,
        "arousal": arousal,
        "dominant_emotion": dominant_emotion,
        "source_confidence": confidence,
    }

    # 1) Child negative emotion
    if child_neg_score >= HIGH_NEGATIVE_CHILD_THRESHOLD:
        sev = Severity.CRITICAL if child_neg_score >= CRITICAL_NEGATIVE_CHILD_THRESHOLD else Severity.HIGH
        signals.append(
            EngineSignal(
                type=SignalType.EMOTION,
                name="high_negative_child_emotion",
                value=child_neg_score,
                severity=sev,
                confidence=confidence,
                details={
                    **details_base,
                    "trigger_threshold": HIGH_NEGATIVE_CHILD_THRESHOLD,
                },
            )
        )

    # 2) Stress pattern: low valence + high arousal
    if valence < STRESS_VALENCE_THRESHOLD and arousal > STRESS_AROUSAL_THRESHOLD:
        signals.append(
            EngineSignal(
                type=SignalType.EMOTION,
                name="stress_pattern_detected",
                value={"valence": valence, "arousal": arousal},
                severity=Severity.HIGH,
                confidence=confidence,
                details={
                    **details_base,
                    "valence_threshold": STRESS_VALENCE_THRESHOLD,
                    "arousal_threshold": STRESS_AROUSAL_THRESHOLD,
                },
            )
        )

    return signals
