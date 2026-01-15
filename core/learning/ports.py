from __future__ import annotations

from typing import List, Optional, Protocol
from core.learning.contracts import LearningSample


class LearningMemoryPort(Protocol):
    def append_sample(self, sample: LearningSample) -> None:
        ...

    def list_samples(self, limit: int = 100) -> List[LearningSample]:
        ...

    def find_by_scene(self, scene_id: str, limit: int = 200) -> List[LearningSample]:
        ...

    def update_outcome(
        self,
        sample_id: str,
        outcome_label: str,
        outcome_notes: Optional[str],
        human_confirmed: bool = True,
    ) -> bool:
        """Returns True if updated, False if sample not found"""
        ...
