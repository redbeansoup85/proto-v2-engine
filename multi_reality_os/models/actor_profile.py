# proto-v2-engine/multi_reality_os/models/actor_profile.py

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class ActorProfile:
    actor_id: str
    name: str
    role: str = "actor"
    group_id: Optional[str] = None

    # 사람마다 다른 가치 기준
    value_weights: Dict[str, float] = field(default_factory=dict)

    # 리스크 허용도: 위험을 어느 정도 감수하나
    risk_tolerance: float = 0.5

    # 변화에 대한 저항감
    change_aversion: float = 0.5

    # 단기형 / 중기형 / 장기형
    time_horizon_pref: str = "mid"
