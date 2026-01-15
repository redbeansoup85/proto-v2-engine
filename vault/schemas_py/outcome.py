from __future__ import annotations

from typing import Any, Dict
from pydantic import Field

from .common import VaultBase


class OutcomeRecord(VaultBase):
    schema: Dict[str, str] = Field(default={"name": "outcome_record", "version": "0.1.0"})
    run_id: str
    pnl: Dict[str, Any]
    excursions: Dict[str, Any]
    execution_quality: Dict[str, Any]
    labels: Dict[str, Any]
    notes: str = ""
