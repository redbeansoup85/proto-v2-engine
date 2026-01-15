from __future__ import annotations

from core.contracts.policy import DecisionMode, Severity, PolicyDecision
from core.contracts.rationale_codes import RationaleCode


class PolicyEngine:
    """
    Minimal stub.
    Replace with your real Policy(v0.2) later.
    """
    def decide(self, *, channel: str, signals: dict) -> PolicyDecision:
        # Very conservative placeholder:
        # - if any obvious risk flag present -> observe_more + critical
        # - else observe_more + medium
        if signals.get("force_low", False) is True:
            return PolicyDecision(
                mode=DecisionMode.observe_more,
                severity=Severity.low,
                rationale_codes=(RationaleCode.NO_ACTION_BY_POLICY,),
            )

        if signals.get("high_risk", False) is True:
            return PolicyDecision(
                mode=DecisionMode.observe_more,
                severity=Severity.critical,
                rationale_codes=(RationaleCode.CRITICAL_BY_POLICY_RULE,),
            )

        return PolicyDecision(
            mode=DecisionMode.observe_more,
            severity=Severity.medium,
            rationale_codes=(RationaleCode.NO_ACTION_BY_POLICY,),
        )
