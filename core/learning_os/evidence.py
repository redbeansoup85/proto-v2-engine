from dataclasses import dataclass
from typing import Dict, Optional
import time
import uuid

@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str

class EvidenceStore:
    """
    Immutable evidence artefact store (v1: in-memory).
    Once created, evidence content must not be mutated.
    """
    def __init__(self):
        self._store: Dict[str, dict] = {}

    def create(self, payload: dict) -> EvidenceRef:
        eid = f"ev-{uuid.uuid4()}"
        record = {"created_at": time.time(), "payload": payload}
        self._store[eid] = record
        return EvidenceRef(evidence_id=eid)

    def read(self, evidence_id: str) -> Optional[dict]:
        return self._store.get(evidence_id)
