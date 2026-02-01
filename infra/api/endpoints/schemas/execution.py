from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


class ExecutionRunRequest(BaseModel):
    project_id: str
    decision_card_id: str  # UUID 문자열로 받는 게 현재 DB/ORM과 가장 안전
    execution_scope: str = Field(default="automation")
    idempotency_key: str


class ExecutionRunResponse(BaseModel):
    execution_id: str
    status: str
    blocked_reason: Optional[str] = None
    dedup_hit: bool = False
    request_fingerprint: str


class ExecutionRunDetailResponse(BaseModel):
    execution_id: str
    project_id: str
    decision_card_id: str
    execution_scope: str
    status: str
    blocked_reason: Optional[str] = None
    idempotency_key: str
    request_fingerprint: str
    created_at: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
