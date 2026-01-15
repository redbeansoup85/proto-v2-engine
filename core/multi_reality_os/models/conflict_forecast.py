# proto-v2-engine/multi_reality_os/models/conflict_forecast.py

from dataclasses import dataclass, field
from typing import List


@dataclass
class ConflictPoint:
    """
    특정 시간 T에서, 특정 Actor에게 갈등/붕괴 위험이 크게 쌓인 지점.
    """
    time_index: int
    actor_id: str
    conflict_score: float   # 0~1
    reason: str             # 예: "high_anxiety", "high_mesh_conflict"


@dataclass
class ConflictForecast:
    """
    하나의 Scene에 대한 전체 갈등 예측 결과.
    """
    scene_id: str

    # T0~Tn 시간축에 따른 평균 '압력(갈등/불안)' 프로파일
    timeline_profile: List[float] = field(default_factory=list)

    # 특정 시점/Actor에 대한 Hotspot 리스트
    hotspots: List[ConflictPoint] = field(default_factory=list)

    # 전체적으로 이 Scene이 붕괴/갈등으로 치닫을 위험도 (0~1)
    overall_risk: float = 0.0
