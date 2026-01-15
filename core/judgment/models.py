from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .status import DecisionStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DpaOption(BaseModel):
    option_id: str
    title: str
    summary: Optional[str] = None
    blocked: bool = False
    blocked_reason: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class HumanDecision(BaseModel):
    selected_option_id: str
    reason_codes: List[str] = Field(default_factory=list)
    reason_note: Optional[str] = None

    approver_name: str
    approver_role: str
    signature: str  # typed name + timestamp is fine for v0

    decided_at: datetime = Field(default_factory=utcnow)


class DpaRecord(BaseModel):
    dpa_id: str
    event_id: str

    status: DecisionStatus = DecisionStatus.DPA_CREATED

    context_json: Dict[str, Any] = Field(default_factory=dict)
    options_json: List[DpaOption] = Field(default_factory=list)
    constraints_json: Dict[str, Any] = Field(default_factory=dict)
    system_position_json: Dict[str, Any] = Field(default_factory=dict)

    human_decision_json: Optional[HumanDecision] = None

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
