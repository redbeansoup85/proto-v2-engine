from __future__ import annotations

from typing import Any, Dict, List
from pydantic import Field

from .common import VaultBase


class ExecutionLog(VaultBase):
    schema: Dict[str, str] = Field(default={"name": "execution_log", "version": "0.1.0"})
    run: Dict[str, Any] = Field(..., description="run_id, card ids, context_id etc.")
    instrument: Dict[str, Any]
    intent: Dict[str, Any]
    risk: Dict[str, Any]
    orders: List[Dict[str, Any]] = Field(default_factory=list)
    fills: List[Dict[str, Any]] = Field(default_factory=list)
    events: List[Dict[str, Any]] = Field(default_factory=list)
