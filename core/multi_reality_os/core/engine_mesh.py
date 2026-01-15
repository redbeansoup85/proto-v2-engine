# proto-v2-engine/multi_reality_os/core/engine_mesh.py

from math import fabs
from typing import Dict, List
from ..models.scene_base import SceneBase
from ..models.perspective_layer import PerspectiveLayer
from ..models.reality_link import RealityLink
from ..models.reality_mesh import RealityMesh


def build_reality_mesh(scene: SceneBase,
                       pls: Dict[str, PerspectiveLayer]) -> RealityMesh:

    links = []
    actors = list(pls.keys())

    for i in range(len(actors)):
        for j in range(i + 1, len(actors)):
            a = actors[i]
            b = actors[j]

            pl_a = pls[a]
            pl_b = pls[b]

            conflict = 0
            align = 0

            for k in scene.structural_pressures.keys():
                pa = pl_a.perceived_pressures.get(k, 0)
                pb = pl_b.perceived_pressures.get(k, 0)
                diff = fabs(pa - pb)
                conflict += diff
                align += 1 - diff

            conflict /= max(len(scene.structural_pressures), 1)
            align /= max(len(scene.structural_pressures), 1)

            links.append(
                RealityLink(
                    from_pl=pl_a.pl_id,
                    to_pl=pl_b.pl_id,
                    conflict_level=conflict,
                    benefit_alignment=align,
                )
            )

    avg_conflict = sum(l.conflict_level for l in links) / max(len(links), 1)
    avg_align = sum(l.benefit_alignment for l in links) / max(len(links), 1)

    collapse_risk = (avg_conflict * 0.7) + (1 - avg_align) * 0.3

    return RealityMesh(
        mesh_id=f"mesh:{scene.scene_id}",
        perspective_layers={k: vars(v) for k, v in pls.items()},
        links=links,
        global_conflict=avg_conflict,
        global_alignment=avg_align,
        collapse_risk=collapse_risk,
    )
