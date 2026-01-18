from __future__ import annotations

from typing import List
from pydantic import BaseModel, Field, model_validator

from core.contracts.actions import ExecutionAction
from core.contracts.meta_judgment_envelope import EnvelopeMeta, Constraints, Audit, HumanApproval


class ExecutionAuthority(BaseModel):
    domain: str = Field(..., min_length=1)
    allowed_actions: List[ExecutionAction] = Field(default_factory=list, min_length=1)
    forbidden_actions: List[ExecutionAction] = Field(default_factory=list)
    confidence_floor: float = Field(..., ge=0.0, le=1.0)


class ExecutionEnvelope(BaseModel):
    meta: EnvelopeMeta
    authority: ExecutionAuthority
    constraints: Constraints
    audit: Audit
    human_approval: HumanApproval

    @model_validator(mode="after")
    def _invariants(self) -> "ExecutionEnvelope":
        overlap = set(self.authority.allowed_actions).intersection(set(self.authority.forbidden_actions))
        if overlap:
            raise ValueError(f"authority.allowed_actions overlaps forbidden_actions: {sorted(overlap)}")
        return self

    def is_expired(self, now=None) -> bool:
        from datetime import datetime, timezone
        now = now or datetime.now(timezone.utc)
        if self.meta.expires_at is None:
            return False
        return now >= self.meta.expires_at
