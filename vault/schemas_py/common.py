from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal
import hashlib
import json

from pydantic import BaseModel, Field, model_validator, ConfigDict


class VaultBase(BaseModel):
    """
    모든 Vault 문서 공통 베이스.
    - schema: {"name": "...", "version": "..."}
    - id: ULID/UUID
    - ts: UTC datetime
    - producer: {"system": "...", "module": "...", "instance": "..."}
    - hash: {"algo": "sha256", "value": "..."}  (문서 전체 canonical JSON 해시; hash 필드 제외)
    """
    model_config = ConfigDict(frozen=True)

    schema: Dict[str, str] = Field(..., description="name/version pair")
    id: str = Field(..., description="ULID or UUID")
    ts: datetime = Field(..., description="UTC ISO8601")
    producer: Dict[str, str] = Field(..., description="system/module/instance")
    hash: Dict[Literal["algo", "value"], str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _compute_hash(self) -> "VaultBase":
        d = self.model_dump(mode="json")
        d.pop("hash", None)
        canonical = json.dumps(d, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        hv = hashlib.sha256(canonical).hexdigest()
        object.__setattr__(self, "hash", {"algo": "sha256", "value": hv})
        return self
