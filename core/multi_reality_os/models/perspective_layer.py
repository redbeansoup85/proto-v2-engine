# proto-v2-engine/multi_reality_os/models/perspective_layer.py

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class PerspectiveLayer:
    """
    하나의 Actor가 '이 Scene을 어떻게 보고 있는지'를 나타내는 레이어.
    """
    pl_id: str
    actor_id: str

    # 이 상황에서 어떤 압력을 얼마나 느끼는지 (Scene의 structural_pressures에 대한 개인 해석)
    perceived_pressures: Dict[str, float] = field(default_factory=dict)

    # 감정/인지 기반 편향 (예: 불안, 기대, 피로 등)
    emotional_bias: Dict[str, float] = field(default_factory=dict)

    # 개인의 목표/우선순위 (예: 안정성, 성장, 비용절감 등)
    priorities: Dict[str, float] = field(default_factory=dict)

    # (옵션) 현재 인지 상태 스냅샷
    # Cognitive Flow에서는 여기서 anxiety, hope 등의 기본 값을 가져다 쓴다.
    emotional_state: Dict[str, float] = field(default_factory=dict)

    # (옵션) 시나리오 전망 (예: "quit", "stay", "accept_role" 등)
    scenario_projection: Dict[str, float] = field(default_factory=dict)
