from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class AgentState:
    anxiety: float
    decision: str
    alignment: float

@dataclass
class EquilibriumStep:
    t: int
    agents: Dict[str, AgentState]
    global_conflict: float
    alignment_avg: float

@dataclass
class EquilibriumResult:
    trajectory: list
    equilibrium_point: Dict[str, Any]
    pattern_type: str
    intervention_sensitivity: Dict[str, float]
