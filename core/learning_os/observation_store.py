from dataclasses import dataclass
from typing import List, Optional
import time


@dataclass(frozen=True)
class Observation:
    ts: float
    # v1: directional signal only (e.g., "up", "down", "neutral")
    direction: str
    # Optional metadata
    meta: Optional[dict] = None


class ObservationStore:
    """
    Append-only store.
    In production, back with persistent storage; here we keep it in-memory.
    """
    def __init__(self):
        self._items: List[Observation] = []

    def append(self, direction: str, meta: Optional[dict] = None, ts: Optional[float] = None) -> Observation:
        obs = Observation(ts=ts if ts is not None else time.time(), direction=direction, meta=meta)
        self._items.append(obs)
        return obs

    def all(self) -> List[Observation]:
        return list(self._items)
