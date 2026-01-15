# proto-v2-engine/multi_reality_os/models/consensus_result.py

from dataclasses import dataclass, field
from typing import List


@dataclass
class ConsensusResult:
    scene_id: str
    recommended_actions: List[str] = field(default_factory=list)
    confidence: float = 0.5
