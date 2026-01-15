from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from core.policy.memory.ports import PolicyMemoryKey, PolicyMemoryPort


@dataclass
class InMemoryPolicyMemory(PolicyMemoryPort):
    _store: Dict[str, Dict[str, Any]]

    def __init__(self) -> None:
        self._store = {}

    def _k(self, key: PolicyMemoryKey) -> str:
        return f"{key.org_id}::{key.site_id}::{key.channel}"

    def load_last_scene_state(self, key: PolicyMemoryKey) -> Optional[Dict[str, Any]]:
        return self._store.get(self._k(key))

    def save_scene_state(self, key: PolicyMemoryKey, scene_state: Dict[str, Any]) -> None:
        self._store[self._k(key)] = scene_state
