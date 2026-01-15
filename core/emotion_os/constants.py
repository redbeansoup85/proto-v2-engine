from __future__ import annotations

from typing import Final

# -------------------------------
# Emotion Feature Keys (v0.1 표준)
# prelude.features에 반드시 이 키들로 넣을 것
# -------------------------------

VALENCE_KEY: Final[str] = "valence"  # float: -1.0 (negative) ~ 1.0 (positive)
AROUSAL_KEY: Final[str] = "arousal"  # float: 0.0 (calm) ~ 1.0 (excited)
DOMINANT_EMOTION_KEY: Final[str] = "dominant_emotion"  # str
CHILD_NEGATIVE_EMOTION_SCORE_KEY: Final[str] = "child_negative_emotion_score"  # float: 0.0 ~ 1.0

# -------------------------------
# Thresholds (v0.1 초기값)
# -------------------------------

HIGH_NEGATIVE_CHILD_THRESHOLD: Final[float] = 0.7
CRITICAL_NEGATIVE_CHILD_THRESHOLD: Final[float] = 0.9

STRESS_VALENCE_THRESHOLD: Final[float] = -0.5
STRESS_AROUSAL_THRESHOLD: Final[float] = 0.6
