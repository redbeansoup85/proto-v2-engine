from dataclasses import dataclass, field
from typing import Dict, List

from .cognitive_node import CognitiveNode


@dataclass
class ActorCognitiveFlow:
    """
    특정 Actor에 대한 시간축 상의 인지·감정 흐름.
    """
    actor_id: str
    nodes: List[CognitiveNode] = field(default_factory=list)


@dataclass
class CognitiveFlowMap:
    """
    하나의 Scene 전체에 대한 인지 흐름 맵.
    - 사건 타임라인 (event_line)
    - 각 Actor별 인지 흐름 (actor_flows)
    """
    scene_id: str
    timeline_length: int

    # 사건 자체의 타임라인 (상단 Event Line에 쓰인다)
    event_line: List[CognitiveNode]

    # 각 Actor별 Cognitive Flow
    actor_flows: Dict[str, ActorCognitiveFlow] = field(default_factory=dict)
