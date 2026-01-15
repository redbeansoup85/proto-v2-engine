from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from infra.api.deps import get_l2

router = APIRouter(prefix="/v1/audit", tags=["audit"])


@router.get("/snapshots")
def list_snapshots(
    limit: int = Query(50, ge=1, le=500),
    l2=Depends(get_l2),
) -> dict:
    items = l2.list_recent_decision_snapshots(limit=limit)
    return {"count": len(items), "items": items}
