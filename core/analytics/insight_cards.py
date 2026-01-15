from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from core.analytics.weekly import rollup_weekly
from core.analytics.explainability import (
    top_scenes_by_severity,
    top_scenes_by_decisions,
)

BASE_API_URL = "http://127.0.0.1:8000"  # UI/배포 시 ENV로 교체 가능


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class InsightCard:
    card_id: str
    title: str
    window_days: int
    ts_generated: str

    headline: str
    bullets: List[str]

    total_scenes: int
    by_channel: Dict[str, int]
    severity_distribution: Dict[str, int]
    top_rationale_codes: List[Tuple[str, int]]

    flags: List[str]

    sample_scene_ids: List[str]

    evidence: Dict[str, List[str]]

    # C-2-δ
    top_scenes_severity: List[dict]
    top_scenes_decisions: List[dict]

    # C-2-ε
    evidence_links: Dict[str, Dict[str, str]]


def _dominant_channel(by_channel: Dict[str, int]) -> Optional[str]:
    if not by_channel:
        return None
    return sorted(by_channel.items(), key=lambda x: x[1], reverse=True)[0][0]


def _severity_max(sev_dist: Dict[str, int]) -> Optional[str]:
    for s in ["critical", "high", "medium", "low"]:
        if sev_dist.get(s, 0) > 0:
            return s
    return None


def build_weekly_insight_card(
    scene_summaries: List[dict],
    days: int = 7,
    scene_to_snapshot_ids: Optional[Dict[str, List[str]]] = None,
    evidence_per_scene: int = 10,
) -> InsightCard:
    r = rollup_weekly(scene_summaries, days=days)

    if scene_to_snapshot_ids is None:
        scene_to_snapshot_ids = {}

    bullets: List[str] = []
    flags: List[str] = []

    # Evidence + links
    evidence: Dict[str, List[str]] = {}
    evidence_links: Dict[str, Dict[str, str]] = {}

    for sid in r.sample_scene_ids:
        evidence[sid] = scene_to_snapshot_ids.get(sid, [])[:evidence_per_scene]
        evidence_links[sid] = {
            "scene_evidence": f"{BASE_API_URL}/v1/scenes/evidence/{sid}",
            "audit_snapshots": f"{BASE_API_URL}/v1/audit/snapshots/by_scene/{sid}",
        }

    top_sev = top_scenes_by_severity(scene_summaries, k=5)
    top_dec = top_scenes_by_decisions(scene_summaries, k=5)

    if r.total_scenes == 0:
        bullets.append("No closed scenes in this window.")
        return InsightCard(
            card_id=f"insight_weekly_{days}d",
            title=f"Weekly Insight ({days}d)",
            window_days=days,
            ts_generated=_now_iso(),
            headline=f"No closed scenes in the last {days} days.",
            bullets=bullets,
            total_scenes=0,
            by_channel={},
            severity_distribution={},
            top_rationale_codes=[],
            flags=["INSUFFICIENT_DATA"],
            sample_scene_ids=[],
            evidence={},
            top_scenes_severity=[],
            top_scenes_decisions=[],
            evidence_links={},
        )

    dom_ch = _dominant_channel(r.by_channel)
    max_sev = _severity_max(r.severity_distribution)

    headline = f"{r.total_scenes} scene(s) closed in the last {days} days."
    if dom_ch:
        headline += f" Dominant channel: {dom_ch}."
    if max_sev:
        bullets.append(f"Highest severity observed: {max_sev}.")

    bullets.append("InsightCard includes direct links to evidence and audit logs.")
    bullets.append("Click scene_id to inspect full decision history.")

    return InsightCard(
        card_id=f"insight_weekly_{days}d",
        title=f"Weekly Insight ({days}d)",
        window_days=days,
        ts_generated=_now_iso(),
        headline=headline,
        bullets=bullets,
        total_scenes=r.total_scenes,
        by_channel=r.by_channel,
        severity_distribution=r.severity_distribution,
        top_rationale_codes=r.top_rationale_codes,
        flags=flags,
        sample_scene_ids=r.sample_scene_ids,
        evidence=evidence,
        top_scenes_severity=top_sev,
        top_scenes_decisions=top_dec,
        evidence_links=evidence_links,
    )
