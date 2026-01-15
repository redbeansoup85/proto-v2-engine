# proto-v2-engine/multi_reality_os/core/builder_perspective.py

from typing import Dict, List
from ..models.perspective_layer import PerspectiveLayer
from ..models.scene_base import SceneBase
from ..models.actor_profile import ActorProfile


def build_perspective_layers(scene: SceneBase,
                             actor_profiles: List[ActorProfile]) -> Dict[str, PerspectiveLayer]:

    pls = {}

    for ap in actor_profiles:
        pl_id = f"{scene.scene_id}:{ap.actor_id}"

        perceived = {}
        for k, v in scene.structural_pressures.items():
            bias = ap.value_weights.get(k, 0.5)
            perceived[k] = (v * 0.7) + (bias * 0.3)

        emotional_bias = {
            "anxiety": max(0, v * 0.5)
            for k, v in ap.value_weights.items()
        }

        priorities = ap.value_weights.copy()

        pl = PerspectiveLayer(
            pl_id=pl_id,
            actor_id=ap.actor_id,
            perceived_pressures=perceived,
            emotional_bias=emotional_bias,
            priorities=priorities,
        )
        pls[ap.actor_id] = pl

    return pls
