from __future__ import annotations

import os
from fastapi import APIRouter, HTTPException

from infra.api.routes.constitutional import router as constitutional_router  # type: ignore

# NOTE:
# This module exists only to isolate debug-only routes from production surface.
# We re-export a dedicated router that will be mounted only in METAOS_ENV=local.

router = APIRouter(prefix="/v1/constitutional", tags=["constitutional:debug"])

# Find the existing debug handler from the main router by attribute access is not feasible.
# v0.6 baseline approach:
# - Keep the debug endpoint implementation here as a thin wrapper that calls the same internal function,
#   OR duplicate minimal debug seed logic here.
#
# If your existing infra/api/routes/constitutional.py currently defines __debug_seed directly,
# MOVE that endpoint function body here and delete it from constitutional.py.

@router.post("/__debug_seed")
def debug_seed(payload: dict):
    if os.getenv("METAOS_ENV", "").lower() != "local":
        raise HTTPException(status_code=404, detail="Not found")
    # Minimal placeholder:
    # Replace this body by moving the existing __debug_seed implementation here.
    return {"ok": False, "detail": "MOVE __debug_seed implementation here (v0.6 isolation)."}
