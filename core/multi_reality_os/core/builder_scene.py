# proto-v2-engine/multi_reality_os/core/builder_scene.py

from datetime import datetime
from typing import Dict, List
from ..models.scene_base import SceneBase


def build_scene(scene_id: str,
                title: str,
                description: str,
                actors: List[str],
                pressures: Dict[str, float] = None,
                constraints: Dict[str, float] = None):

    return SceneBase(
        scene_id=scene_id,
        title=title,
        description=description,
        timepoint=datetime.utcnow(),
        actor_ids=actors,
        structural_pressures=pressures or {},
        constraints=constraints or {},
    )
