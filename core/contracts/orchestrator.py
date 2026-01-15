# core/contracts/orchestrator.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any

from core.contracts._compat import StrEnum


# =============================================================================
# Orchestrator routing contracts (v1 lock compatible)
#
# Goal:
# - Keep Orchestrator execution-free (auto_action must remain False)
# - Provide stable types used by core/orchestrator/router.py
#
# NOTE:
# - These are "routing-layer" contracts (DeliveryPlan/DeliveryRouting/Recommendation).
# - Gate 1/2 contracts (Responsibility/ExecutionAuthorizationRequest) live below.
# =============================================================================


# =========================
# v0.3/v1 Orchestrator Types
# =========================

class DeliveryPlan(StrEnum):
    """
    Routing plan enumeration.

    Keep values stable: they may appear in logs, audit artifacts, and demos.
    """
    HOLD_AND_HUMAN_REVIEW = "HOLD_AND_HUMAN_REVIEW"
    NOTIFY_MANAGER = "NOTIFY_MANAGER"
    ALERT_ONLY = "ALERT_ONLY"


@dataclass(frozen=True)
class Recommendation:
    """
    A minimal recommendation payload routed by the orchestrator.

    Aligned with core/orchestrator/router.py usage:
    - type / code / message
    """
    type: str                    # e.g., "alert" | "notify"
    code: str                    # e.g., "HOLD" | "NOTIFY_MANAGER" | "ALERT_ONLY"
    message: str                 # human-readable
    payload: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class DeliveryRouting:
    """
    Where/how the recommendation bundle should be delivered.

    Invariant:
    - auto_action MUST remain False (Meta OS does not execute).
    """
    delivery_plan: DeliveryPlan
    auto_action: bool = False     # MUST remain False
    destination: str = "vault"    # "vault" | "queue" | "manual"
    queue_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


def assert_execution_free(routing: "DeliveryRouting") -> None:
    assert routing is not None, "DeliveryRouting required"
    assert routing.auto_action is False, "auto_action MUST remain false"


# =============================================================================
# Gate 1 — Responsibility (v1 lock)
# =============================================================================

class ResponsibilityDecision(StrEnum):
    ACCEPT = "ACCEPT"   # accept responsibility
    REJECT = "REJECT"   # explicit reject (still logged)


@dataclass(frozen=True)
class ResponsibilityAcceptance:
    """
    Gate 1 output.
    Human explicitly accepts responsibility for a judgment artifact.

    NOTE:
    - This is NOT execution.
    - This is an accountability object.
    """
    decision: ResponsibilityDecision
    actor_id: str
    actor_role: str
    ts: str  # ISO8601 string (keep simple & dependency-free)
    judgment_ref: str  # reference id/path/hash to the judgment receipt/artifact
    reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def is_accepted(self) -> bool:
        return self.decision == ResponsibilityDecision.ACCEPT


# =============================================================================
# Gate 2 — Execution Authorization (v1 lock)
# =============================================================================

@dataclass(frozen=True)
class ExecutionScope:
    """
    What is permitted to be executed (bounded).
    Example: asset list, allowed action types, account, venue/channel, etc.
    """
    domain: str  # "family" | "internal_enterprise" | "external_enterprise"
    permitted_actions: Tuple[str, ...] = ()
    assets: Tuple[str, ...] = ()
    account_id: Optional[str] = None
    target_id: Optional[str] = None  # e.g., "binance_spot", "ibkr", "ops_manual"
    notes: Optional[str] = None


@dataclass(frozen=True)
class ExecutionLimit:
    """
    How much is permitted (bounded).
    Keep it minimal for v1.0; extend later.
    """
    max_notional_usd: Optional[float] = None
    max_order_count: Optional[int] = None
    max_daily_loss_usd: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class ExecutionTimebox:
    """
    When the authorization is valid.
    """
    valid_from: str   # ISO8601
    valid_until: str  # ISO8601


@dataclass(frozen=True)
class ExecutionAuthorizationRequest:
    """
    Gate 2 output.
    A non-executing request that an external executor may consume.

    IMPORTANT invariants:
    - auto_action MUST remain False.
    - responsibility must be ACCEPTED.
    """
    auto_action: bool = False  # MUST remain false (invariant)

    responsibility: Optional[ResponsibilityAcceptance] = None  # must be accepted
    scope: Optional[ExecutionScope] = None
    limit: Optional[ExecutionLimit] = None
    timebox: Optional[ExecutionTimebox] = None

    # linkage
    judgment_ref: str = ""  # should match responsibility.judgment_ref
    request_payload: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


def assert_responsibility_accepted(r: "ResponsibilityAcceptance") -> None:
    assert r is not None, "ResponsibilityAcceptance required"
    assert r.is_accepted(), "Responsibility must be explicitly ACCEPTED"
    assert getattr(r, "actor_id", None), "actor_id required"
    assert getattr(r, "judgment_ref", None), "judgment_ref required"


def assert_execution_request_valid(req: "ExecutionAuthorizationRequest") -> None:
    assert req is not None, "ExecutionAuthorizationRequest required"
    assert req.auto_action is False, "auto_action MUST remain false"
    assert req.responsibility is not None, "responsibility required"
    assert_responsibility_accepted(req.responsibility)

    assert req.scope is not None, "scope required"
    assert req.limit is not None, "limit required"
    assert req.timebox is not None, "timebox required"

    assert getattr(req, "judgment_ref", None), "judgment_ref required"
    # recommended invariant
    assert req.judgment_ref == req.responsibility.judgment_ref, "judgment_ref mismatch"
