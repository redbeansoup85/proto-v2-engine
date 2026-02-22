from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter

from infra.risk.regime import get_regime_warden

router = APIRouter(tags=["risk"])


@router.get("/api/risk/regime")
def get_risk_regime() -> dict[str, Any]:
    warden = get_regime_warden()
    snap = warden.snapshot(now_ms=int(time.time() * 1000)).as_dict()
    return {
        "current_regime": snap["current_regime"],
        "target_regime": snap["target_regime"],
        "reasons": snap["reasons"],
        "missing": snap["missing"],
        "entered_at": snap["entered_at"],
        "normalized_since": snap["normalized_since"],
        "cooldown_remaining_ms": snap["cooldown_remaining_ms"],
    }
