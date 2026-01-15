from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from core.contracts.policy import Channel


@dataclass(frozen=True)
class InsightCard:
    insight_id: str
    channel: Channel
    title: str
    summary: str
    evidence_metrics: Tuple[dict, ...] = ()
    scope: Optional[dict] = None  # e.g. {"context_key": "...", "period": "2025-W51"}


@dataclass(frozen=True)
class TrendReportRef:
    report_id: str
    period: str          # e.g. "2025-W51" or "2025-12"
    channel: Channel
    generated_ts: str
