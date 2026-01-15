from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Protocol

from .errors import conflict
from .models import DpaRecord


class DpaRepository(Protocol):
    def get(self, dpa_id: str) -> Optional[DpaRecord]: ...
    def create(self, dpa: DpaRecord) -> DpaRecord: ...
    def save(self, dpa: DpaRecord) -> DpaRecord: ...


@dataclass
class InMemoryDpaRepository:
    _store: Dict[str, DpaRecord]

    def __init__(self) -> None:
        self._store = {}

    def get(self, dpa_id: str) -> Optional[DpaRecord]:
        return self._store.get(dpa_id)

    def create(self, dpa: DpaRecord) -> DpaRecord:
        if dpa.dpa_id in self._store:
            raise conflict("DPA_ALREADY_EXISTS", "DPA with same id already exists.", {"dpa_id": dpa.dpa_id})
        self._store[dpa.dpa_id] = dpa
        return dpa

    def save(self, dpa: DpaRecord) -> DpaRecord:
        if dpa.dpa_id not in self._store:
            raise conflict("DPA_NOT_FOUND", "DPA not found for save.", {"dpa_id": dpa.dpa_id})
        self._store[dpa.dpa_id] = dpa
        return dpa
