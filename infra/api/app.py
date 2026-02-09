from fastapi import FastAPI

from infra.api.endpoints.approvals import router as approvals_router
from infra.api.endpoints.execution import router as execution_router


def create_app() -> FastAPI:
    app = FastAPI()

    # API v1
    app.include_router(execution_router, prefix="/api/v1")
    app.include_router(approvals_router, prefix="/api/v1")

    return app


app = create_app()
