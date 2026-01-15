from __future__ import annotations

import json
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from infra.api.deps import get_l2

router = APIRouter(prefix="/v1/scenes", tags=["scenes"])


@router.get("/closed")
def list_closed(
    limit: int = Query(50, ge=1, le=500),
    channel: Optional[str] = Query(None),
    l2=Depends(get_l2),
) -> dict:
    path = getattr(l2, "scene_summaries_path", None)
    if not path:
        return {"count": 0, "items": [], "note": "scene_summaries_path not configured"}

    if not os.path.exists(path):
        return {"count": 0, "items": [], "note": "scene_summaries.jsonl not found yet"}

    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f.readlines() if ln.strip()]

    # latest first
    lines.reverse()

    items: List[dict] = []
    for ln in lines:
        try:
            obj = json.loads(ln)
        except Exception:
            continue
        if channel and obj.get("context", {}).get("channel") != channel:
            continue
        items.append(obj)
        if len(items) >= limit:
            break

    return {"count": len(items), "items": items}
