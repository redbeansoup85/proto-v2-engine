from __future__ import annotations

from typing import Any, Dict, List

from core.orchestrator.contracts import DeliveryPlan, OrchestratorDecision


def _priority_from_severity(sev: str) -> str:
    s = (sev or "").lower()
    if s in ("critical",):
        return "urgent"
    if s in ("high",):
        return "high"
    if s in ("medium",):
        return "normal"
    return "low"


class RecommendationRouter:
    """채널/심각도 기반: 실행이 아닌 '전달 계획(DeliveryPlan)' 산출 (v0.3)."""

    def route(
        self,
        channel: str | None,
        severity: str | None,
        decision_mode: str | None,
        recs: List[Dict[str, Any]],
        *,
        meta: Dict[str, Any] | None = None,
    ) -> OrchestratorDecision:
        ch = channel or "unknown"
        sev = (severity or "low").lower()
        mode = (decision_mode or "").lower()

        priority = _priority_from_severity(sev)
        meta = meta or {}

        # default deliveries: 항상 감사 로그는 남긴다
        deliveries: List[DeliveryPlan] = [
            DeliveryPlan(
                channel="log",
                target="audit_log",
                template="AUDIT_V0_3",
                payload={
                    "channel": ch,
                    "severity": sev,
                    "decision_mode": mode,
                    "recommendations": recs,
                    **meta,
                },
            )
        ]

        # childcare: 절대 자동 실행 X (무조건 human review)
        if ch == "childcare":
            deliveries.append(
                DeliveryPlan(
                    channel="console",
                    target="stdout",
                    template="CHILDCARE_ALERT_V0_3",
                    payload={"severity": sev, "recommendations": recs, **meta},
                )
            )
            return OrchestratorDecision(
                mode="HOLD",
                priority=priority,
                requires_human_review=True,
                reason="human_review_required",
                deliveries=deliveries,
                audit={"policy": "no_auto_execute_childcare", **meta},
            )

        # fnb: 매니저 알림 (severity high 이상이면 urgent 채널)
        if ch == "fnb":
            slack_target = "#ops-alerts" if sev in ("high", "critical") else "#ops"
            deliveries.append(
                DeliveryPlan(
                    channel="slack",
                    target=slack_target,
                    template="FNB_NOTIFY_V0_3",
                    payload={"severity": sev, "recommendations": recs, **meta},
                )
            )
            return OrchestratorDecision(
                mode="NOTIFY_MANAGER",
                priority=priority,
                requires_human_review=(sev in ("high", "critical")),
                reason="notify_manager",
                deliveries=deliveries,
                audit={"policy": "notify_manager_fnb", **meta},
            )

        # trading: 알림만 (자동 주문/실행은 여기서 금지)
        if ch == "trading":
            deliveries.append(
                DeliveryPlan(
                    channel="console",
                    target="stdout",
                    template="TRADING_ALERT_ONLY_V0_3",
                    payload={"severity": sev, "recommendations": recs, **meta},
                )
            )
            return OrchestratorDecision(
                mode="ALERT_ONLY",
                priority=priority,
                requires_human_review=False,
                reason="alert_only_trading",
                deliveries=deliveries,
                audit={"policy": "no_trade_execution_here", **meta},
            )

        # unknown: 로그만
        return OrchestratorDecision(
            mode="LOG_ONLY",
            priority=priority,
            requires_human_review=False,
            reason="unknown_channel_log_only",
            deliveries=deliveries,
            audit={"policy": "default_log_only", **meta},
        )
