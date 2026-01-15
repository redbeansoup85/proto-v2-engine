from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class CognitiveNode:
    """
    시간축 상의 한 지점(T0, T1, T2...)에서
    '무엇을 생각했고, 무엇을 느꼈는지, 어떤 방향으로 기울었는지'를 나타내는 단위 노드.
    """
    time_index: int              # T0, T1, ...
    label: str                   # 간단 제목 예: "책임 증가 인지"
    thought: str                 # 자연어 설명

    # 감정 상태 벡터 (예: {"anxiety":0.7, "hope":0.3})
    emotion: Dict[str, float] = field(default_factory=dict)

    # 선택 경향: 상황을 향해 다가가는지(approach), 피하는지(avoid), 고민 중인지(consider)
    decision_tendency: Optional[str] = None   # "approach" | "avoid" | "consider"

    # 해당 선택 방향에 대한 확신도 (0~1)
    decision_strength: float = 0.0

    # 이 시점이 전체 상황에서 얼마나 중요한지 (0~1)
    significance: float = 0.5
