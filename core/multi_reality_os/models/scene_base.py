# proto-v2-engine/multi_reality_os/models/scene_base.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class SceneBase:
    scene_id: str
    title: str
    description: str
    timepoint: datetime

    location: Optional[str] = None
    context_tags: List[str] = field(default_factory=list)

    actor_ids: List[str] = field(default_factory=list)

    # 상황에 작용하는 압력 구조
    structural_pressures: Dict[str, float] = field(default_factory=dict)

    # 예: 시간 제약, 공간 제약, 규칙 등의 시스템적 제약
    constraints: Dict[str, float] = field(default_factory=dict)
