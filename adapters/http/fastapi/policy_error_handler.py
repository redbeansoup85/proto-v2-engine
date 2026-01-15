from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from core.judgment.errors import PolicyError


async def policy_error_handler(_: Request, exc: PolicyError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "code": exc.code,
            "message": exc.detail,
            "meta": exc.meta,
        },
    )
