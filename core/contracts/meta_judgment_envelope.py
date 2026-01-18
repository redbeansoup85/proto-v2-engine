from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Literal

from pydantic import BaseModel, Field

TraceLevel = Literal["minimal", "standard", "full"]
RetentionPolicy = Literal["volatile", "append_only", "immutable"]


class EnvelopeMeta(BaseModel):
    contract_id: str = Field(..., min_length=8)
    issued_at: datetime
    expires_at: Optional[datetime] = None
    issuer: str = Field(..., min_length=3)
    version: str = Field(..., min_length=3)


class ResourceCeiling(BaseModel):
    cpu_pct: float = Field(..., ge=0.0, le=100.0)
    mem_mb: int = Field(..., ge=1)


class DataScope(BaseModel):
    allowed_sources: List[str] = Field(default_factory=list, min_length=1)
    forbidden_sources: List[str] = Field(default_factory=list)


class Constraints(BaseModel):
    latency_budget_ms: int = Field(..., ge=1)
    resource_ceiling: ResourceCeiling
    data_scope: DataScope


class Audit(BaseModel):
    trace_level: TraceLevel
    retention_policy: RetentionPolicy


class HumanApproval(BaseModel):
    approver_id: str = Field(..., min_length=3)
    approval_ref: str = Field(..., min_length=3)
