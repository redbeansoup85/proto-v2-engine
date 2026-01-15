from __future__ import annotations

from fastapi import HTTPException
from typing import NoReturn

from core.judgment.errors import PolicyError


def raise_http(e: PolicyError) -> NoReturn:
    """
    Convert core PolicyError into FastAPI HTTPException.

    This is the ONLY place where:
      - HTTP status codes
      - response shape
    are decided for judgment errors.

    Routers must not reinterpret core errors.
    """
    raise HTTPException(
        status_code=e.http_status,
        detail={
            "code": e.code,
            "message": e.detail,
            "meta": e.meta,
        },
    )
