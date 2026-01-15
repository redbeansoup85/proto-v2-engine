from __future__ import annotations

import os
from fastapi import APIRouter, Depends, Query

from infra.api.deps import get_l2
from core.analytics.weekly import load_scene_summaries_jsonl
from core.analytics.insight_cards import build_weekly_insight_card
from core.analytics.evidence import (
    load_decision_snapshots_jsonl,
    build_scene_to_snapshot_ids,
    resolve_decision_snapshots_path,
)

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


@router.get("/insight_cards")
def insight_cards(
    days: int = Query(7, ge=1, le=90),
    include_evidence: bool = Query(False),
    evidence_per_scene: int = Query(10, ge=1, le=50),
    l2=Depends(get_l2),
) -> dict:
    # scene summaries
    summaries_path = getattr(l2, "scene_summaries_path", None)
    if not summaries_path or not os.path.exists(summaries_path):
        card = build_weekly_insight_card([], days=days)
        return {"ok": True, "days": days, "cards": [card.__dict__], "note": "scene_summaries.jsonl not found"}

    summaries = load_scene_summaries_jsonl(summaries_path)

    scene_to_snapshot_ids = None
    if include_evidence:
        snap_path = resolve_decision_snapshots_path(l2)
        if snap_path and os.path.exists(snap_path):
            snaps = load_decision_snapshots_jsonl(snap_path)
            scene_to_snapshot_ids = build_scene_to_snapshot_ids(snaps, limit_per_scene=50)
        else:
            scene_to_snapshot_ids = {}

    card = build_weekly_insight_card(
        summaries,
        days=days,
        scene_to_snapshot_ids=scene_to_snapshot_ids,
        evidence_per_scene=evidence_per_scene,
    )
    return {"ok": True, "days": days, "cards": [card.__dict__]}
