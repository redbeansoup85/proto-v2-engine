from __future__ import annotations

from core.contracts.orchestrator import DeliveryPlan, DeliveryRouting, Recommendation
from core.contracts.policy import Channel, Severity
from core.contracts.rationale_codes import RationaleCode


class Orchestrator:
    """
    Minimal stub.
    Must remain execution-free (auto_action=False).
    """
    def route(self, *, channel: Channel, severity: Severity) -> tuple[DeliveryRouting, tuple[Recommendation, ...], tuple[RationaleCode, ...]]:
        # Channel-aware routing (your agreed intent)
        if channel == Channel.childcare:
            routing = DeliveryRouting(delivery_plan=DeliveryPlan.HOLD_AND_HUMAN_REVIEW, auto_action=False)
            recs = (Recommendation(type="alert", code="HOLD", message="High-risk pattern detected. Human review required."),)
            extra = (RationaleCode.CHILDCARE_HUMAN_REVIEW_REQUIRED, RationaleCode.AUTO_INTERVENTION_BLOCKED)
            return routing, recs, extra

        if channel == Channel.fnb:
            routing = DeliveryRouting(delivery_plan=DeliveryPlan.NOTIFY_MANAGER, auto_action=False)
            recs = (Recommendation(type="notify", code="NOTIFY_MANAGER", message="Risk pattern detected. Notify manager for review."),)
            extra = (RationaleCode.AUTO_INTERVENTION_BLOCKED,)
            return routing, recs, extra

        # trading default
        routing = DeliveryRouting(delivery_plan=DeliveryPlan.ALERT_ONLY, auto_action=False)
        recs = (Recommendation(type="alert", code="ALERT_ONLY", message="Advisory alert. No automatic action."),)
        extra = (RationaleCode.AUTO_INTERVENTION_BLOCKED,)
        return routing, recs, extra
