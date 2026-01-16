from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import FastAPI

from infra.api.routes.constitutional import router as constitutional_router


def _is_devlike() -> bool:
    return os.getenv("METAOS_ENV", "dev").lower() in ("dev", "local")


app = FastAPI(title="proto-v2-engine", version="v0.6")


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "service": "proto-v2-engine", "version": "v0.6"}


# Always-on (prod 포함) — constitutional boundary
app.include_router(constitutional_router)

# DEV/LOCAL only — debug surface (lazy import to avoid prod import)
if _is_devlike():
    try:
        from infra.api.routes.constitutional_debug import router as constitutional_debug_router  # noqa: F401
        app.include_router(constitutional_debug_router)
    except Exception:
        # Fail-closed: debug router missing or broken should not break main app
        pass
