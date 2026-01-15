from __future__ import annotations

import os
from fastapi import APIRouter, Depends, Query

from infra.api.deps import get_l2
from core.analytics.evidence import (
    load_decision_snapshots_jsonl,
    build_scene_to_snapshot_ids,
    resolve_decision_snapshots_path,
)

router = APIRouter(prefix="/v1/scenes", tags=["scenes"])


@router.get("/evidence/{scene_id}")
def scene_evidence(
    scene_id: str,
    limit: int = Query(50, ge=1, le=500),
    l2=Depends(get_l2),
) -> dict:
    snap_path = resolve_decision_snapshots_path(l2)
    if not snap_path or not os.path.exists(snap_path):
        return {"ok": True, "scene_id": scene_id, "snapshot_ids": [], "note": "decision_snapshots.jsonl not found"}

    snaps = load_decision_snapshots_jsonl(snap_path)
    m = build_scene_to_snapshot_ids(snaps, limit_per_scene=limit)
    return {"ok": True, "scene_id": scene_id, "snapshot_ids": m.get(scene_id, [])}
