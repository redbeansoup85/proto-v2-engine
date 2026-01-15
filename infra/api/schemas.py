from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from core.contracts.policy import Channel, DecisionMode, Severity
from core.contracts.orchestrator import DeliveryPlan


class WindowModel(BaseModel):
    start_ts: str
    end_ts: str


class MetaModel(BaseModel):
    org_id: str
    site_id: str
    scene_id: Optional[str] = None
    channel: Channel
    window: WindowModel


class DecisionIn(BaseModel):
    meta: MetaModel
    signals: Dict[str, Any] = Field(default_factory=dict)


class PolicyDecisionOut(BaseModel):
    mode: DecisionMode
    severity: Severity
    rationale_codes: List[str]


class OrchestratorOut(BaseModel):
    delivery_plan: DeliveryPlan
    auto_action: bool = False


class DecisionOut(BaseModel):
    meta: MetaModel
    policy_decision: PolicyDecisionOut
    policy_memory_snapshot: Dict[str, Any]
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    orchestrator_routing: OrchestratorOut
