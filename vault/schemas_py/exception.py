from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import Field

from .common import VaultBase


class ExceptionReport(VaultBase):
    schema: Dict[str, str] = Field(default={"name": "exception_report", "version": "0.1.0"})
    run_id: Optional[str] = None
    severity: str = Field(..., pattern="^(HARD_FAIL|WARNING)$")
    code: str
    message: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
