from __future__ import annotations

from fastapi import FastAPI

from infra.api.routes.decision import router as decision_router
from infra.api.routes.audit import router as audit_router
from infra.api.routes.scene import router as scene_router
from infra.api.routes.closed_scenes import router as closed_scenes_router
from infra.api.routes.scene_evidence import router as scene_evidence_router
from infra.api.routes.audit_by_scene import router as audit_by_scene_router
from infra.api.routes.analytics import router as analytics_router
from infra.api.routes.insight_cards import router as insight_cards_router
from infra.api.routes.learning import router as learning_router
from infra.api.routes.policy_patches import router as policy_patches_router


app = FastAPI(
    title="Meta OS API",
    version="0.1.0",
)

app.include_router(decision_router)
app.include_router(audit_router)
app.include_router(scene_router)
app.include_router(closed_scenes_router)
app.include_router(scene_evidence_router)
app.include_router(audit_by_scene_router)
app.include_router(analytics_router)
app.include_router(insight_cards_router)
app.include_router(learning_router)
app.include_router(policy_patches_router)


@app.get("/health")
def health() -> dict:
    return {"ok": True}
