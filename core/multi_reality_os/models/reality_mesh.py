# proto-v2-engine/multi_reality_os/models/reality_mesh.py

from dataclasses import dataclass, field
from typing import List, Dict

from .reality_link import RealityLink


@dataclass
class RealityMesh:
    mesh_id: str
    perspective_layers: Dict[str, dict]  # raw PL dict for now
    links: List[RealityLink] = field(default_factory=list)

    global_conflict: float = 0.0
    global_alignment: float = 0.0
    collapse_risk: float = 0.0
