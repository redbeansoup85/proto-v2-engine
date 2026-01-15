# proto-v2-engine/multi_reality_os/core/engine_consensus.py

from ..models.consensus_result import ConsensusResult
from ..models.reality_mesh import RealityMesh


def compute_consensus(mesh: RealityMesh) -> ConsensusResult:

    actions = []

    if mesh.collapse_risk > 0.7:
        actions.append("Immediate conflict mediation needed.")
    elif mesh.global_conflict > 0.5:
        actions.append("Align perspectives through guided dialog.")
    else:
        actions.append("Proceed with planned action. Alignment sufficient.")

    confidence = 1 - mesh.collapse_risk

    return ConsensusResult(
        scene_id=mesh.mesh_id,
        recommended_actions=actions,
        confidence=confidence,
    )
