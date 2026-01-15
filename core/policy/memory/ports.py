from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Protocol, Tuple, Any


@dataclass(frozen=True)
class PolicyMemoryKey:
    org_id: str
    site_id: str
    channel: str


class PolicyMemoryPort(Protocol):
    def load_last_scene_state(self, key: PolicyMemoryKey) -> Optional[Dict[str, Any]]:
        ...

    def save_scene_state(self, key: PolicyMemoryKey, scene_state: Dict[str, Any]) -> None:
        ...
