from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class PolicyError(Exception):
    """
    Core-level policy error.

    code: stable machine-readable code
    http_status: intended mapping (403/409/422)
    detail: human readable
    meta: optional structured diagnostics
    """

    code: str
    http_status: int
    detail: str
    meta: Optional[Dict[str, Any]] = None


def forbidden(code: str, detail: str, meta: Optional[Dict[str, Any]] = None) -> PolicyError:
    return PolicyError(code=code, http_status=403, detail=detail, meta=meta)


def conflict(code: str, detail: str, meta: Optional[Dict[str, Any]] = None) -> PolicyError:
    return PolicyError(code=code, http_status=409, detail=detail, meta=meta)


def unprocessable(code: str, detail: str, meta: Optional[Dict[str, Any]] = None) -> PolicyError:
    return PolicyError(code=code, http_status=422, detail=detail, meta=meta)
