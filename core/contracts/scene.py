from __future__ import annotations

from dataclasses import dataclass
from core.contracts._compat import StrEnum
from typing import Optional, Tuple

from core.contracts.policy import Channel, Severity
from core.contracts.rationale_codes import RationaleCode


class SceneStatus(StrEnum):
    IDLE = "IDLE"
    OPEN = "OPEN"
    ACTIVE = "ACTIVE"
    RESOLVING = "RESOLVING"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class SceneContext:
    org_id: str
    site_id: str
    channel: Channel
    context_key: str  # hashed, non-identifying


@dataclass(frozen=True)
class SceneRef:
    scene_id: str
    status: SceneStatus
    context: SceneContext
    ts_start: str
    ts_end: Optional[str] = None


@dataclass(frozen=True)
class SceneSummary:
    scene_id: str
    context: SceneContext
    ts_start: str
    ts_end: str
    peak_severity: Severity
    total_decisions: int
    key_rationale_codes: Tuple[RationaleCode, ...]
    delivery_types: Tuple[str, ...]          # e.g. ("HOLD_AND_HUMAN_REVIEW", "NOTIFY_MANAGER")
    human_interventions: Tuple[str, ...]     # type-only, no identities
    outcome_label: Optional[str] = None      # optional learning label at scene level
