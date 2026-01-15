from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from infra.api.deps import get_l3_learning

router = APIRouter(prefix="/v1/learning", tags=["learning"])


class OutcomeIn(BaseModel):
    sample_id: str
    outcome_label: str
    outcome_notes: Optional[str] = None
    human_confirmed: bool = True


@router.post("/outcome")
def set_outcome(payload: OutcomeIn, l3=Depends(get_l3_learning)) -> dict:
    ok = l3.update_outcome(
        sample_id=payload.sample_id,
        outcome_label=payload.outcome_label,
        outcome_notes=payload.outcome_notes,
        human_confirmed=payload.human_confirmed,
    )
    return {"ok": ok, "sample_id": payload.sample_id}


@router.get("/latest")
def latest(limit: int = 50, l3=Depends(get_l3_learning)) -> dict:
    items = l3.list_samples(limit=limit)
    return {"count": len(items), "items": [i.__dict__ for i in items]}
