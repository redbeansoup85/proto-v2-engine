from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class OrchestratorInput:
    org_id: str
    site_id: str
    scene_id: Optional[str]
    channel: Optional[str]

    severity: str
    decision_mode: str

    scene_state: Dict[str, Any]
    recommendations: List[Dict[str, Any]]


@dataclass(frozen=True)
class DeliveryPlan:
    """실행이 아니라 '전달 계획'만 담는다 (read-only)."""
    channel: str              # e.g., "log", "slack", "email", "console"
    target: str               # e.g., "#ops-alerts", "manager@...", "stdout"
    template: str             # e.g., "ALERT_V0_3"
    payload: Dict[str, Any]


@dataclass(frozen=True)
class OrchestratorDecision:
    mode: str                 # HOLD / NOTIFY_MANAGER / ALERT_ONLY / LOG_ONLY
    priority: str             # low / normal / high / urgent
    requires_human_review: bool
    reason: str
    deliveries: List[DeliveryPlan]
    audit: Dict[str, Any]
