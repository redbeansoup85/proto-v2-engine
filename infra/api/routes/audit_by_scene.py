from __future__ import annotations

import json
import os
from fastapi import APIRouter, Depends, Query

from infra.api.deps import get_l2
from core.analytics.evidence import resolve_decision_snapshots_path

router = APIRouter(prefix="/v1/audit", tags=["audit"])


@router.get("/snapshots/by_scene/{scene_id}")
def snapshots_by_scene(
    scene_id: str,
    limit: int = Query(50, ge=1, le=500),
    l2=Depends(get_l2),
) -> dict:
    path = resolve_decision_snapshots_path(l2)
    if not path or not os.path.exists(path):
        return {"count": 0, "items": [], "note": "decision_snapshots.jsonl not found"}

    items = []
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f.readlines() if ln.strip()]
    lines.reverse()  # latest first

    for ln in lines:
        try:
            obj = json.loads(ln)
        except Exception:
            continue
        meta = obj.get("meta") or {}
        sid = meta.get("scene_id") or (obj.get("scene") or {}).get("scene_id")
        if sid != scene_id:
            continue
        items.append(obj)
        if len(items) >= limit:
            break

    return {"count": len(items), "items": items}
