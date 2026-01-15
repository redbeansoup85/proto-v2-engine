from __future__ import annotations

import os
from fastapi import APIRouter, Depends, Query

from infra.api.deps import get_l2
from core.analytics.weekly import load_scene_summaries_jsonl, rollup_weekly

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


@router.get("/weekly")
def weekly(days: int = Query(7, ge=1, le=90), l2=Depends(get_l2)) -> dict:
    path = getattr(l2, "scene_summaries_path", None)
    if not path or not os.path.exists(path):
        return {"ok": True, "days": days, "note": "scene_summaries.jsonl not found", "rollup": None}

    items = load_scene_summaries_jsonl(path)
    rollup = rollup_weekly(items, days=days)
    return {"ok": True, "days": days, "rollup": rollup.__dict__}
