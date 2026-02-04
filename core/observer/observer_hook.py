from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from infra.api.audit_sink import emit_audit_event


def emit_shadow_observation(
    *,
    outcome: str,
    reason_code: str,
    adapter_name: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Non-blocking Observer Hook for shadow execution signals.

    Contract:
      - MUST NOT raise
      - MUST NOT include request/response payload
      - records only reason_code + minimal metadata
    """
    event: Dict[str, Any] = {
        "event": "SHADOW_OBSERVATION",
        "action": "shadow_adapter",
        "outcome": outcome,
        "reason_code": reason_code,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    if adapter_name:
        event["adapter_name"] = adapter_name
    if meta:
        event["meta"] = meta

    try:
        emit_audit_event(event)
    except Exception:
        return
