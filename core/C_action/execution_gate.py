from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from core.contracts.orchestrator import (
    ExecutionAuthorizationRequest,
    ExecutionScope,
    ExecutionLimit,
    ExecutionTimebox,
    ResponsibilityAcceptance,
    assert_execution_request_valid,
)

# execution-class channels: MUST carry a valid ExecutionAuthorizationRequest
EXECUTION_CHANNELS = {
    "trading",
    "ops_exec",
    "automation",
    "live",
}


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _require_dict(x: Any, *, name: str) -> Dict[str, Any]:
    if not isinstance(x, dict):
        raise ValueError(f"{name} must be an object")
    return x


def _coerce_execution_request(raw: Dict[str, Any]) -> ExecutionAuthorizationRequest:
    """
    Explicit reconstruction (no implicit magic):
    - responsibility/scope/limit/timebox are rebuilt into dataclasses
    so downstream invariants (e.g., is_accepted()) cannot break.
    """
    resp_raw = _require_dict(raw.get("responsibility"), name="execution_request.responsibility")
    responsibility = ResponsibilityAcceptance(**resp_raw)

    scope_raw = _require_dict(raw.get("scope"), name="execution_request.scope")
    scope = ExecutionScope(**scope_raw)

    limit_raw = _require_dict(raw.get("limit"), name="execution_request.limit")
    limit = ExecutionLimit(**limit_raw)

    timebox_raw = _require_dict(raw.get("timebox"), name="execution_request.timebox")
    timebox = ExecutionTimebox(**timebox_raw)

    req = ExecutionAuthorizationRequest(
        auto_action=bool(raw.get("auto_action", False)),
        responsibility=responsibility,
        scope=scope,
        limit=limit,
        timebox=timebox,
        judgment_ref=str(raw.get("judgment_ref") or ""),
        request_payload=raw.get("request_payload"),
        metadata=raw.get("metadata"),
    )
    return req


def enforce_execution_gate_for_queue_item(q: Dict[str, Any]) -> None:
    """
    If a queue item is for an execution-class channel,
    it must carry a valid ExecutionAuthorizationRequest artifact path.

    Accepts either:
    - q["meta"]["execution_request_path"]
    - q["execution_request_path"]
    """
    channel = q.get("channel") or (q.get("plan") or {}).get("channel")
    if channel not in EXECUTION_CHANNELS:
        return

    meta = q.get("meta") or {}
    exec_req_path: Optional[str] = None
    if isinstance(meta, dict):
        exec_req_path = meta.get("execution_request_path")
    if not exec_req_path:
        exec_req_path = q.get("execution_request_path")

    if not exec_req_path:
        raise ValueError(
            f"Execution gate required for channel={channel}: missing execution_request_path"
        )

    if not os.path.exists(exec_req_path):
        raise ValueError(
            f"execution_request_path does not exist: {exec_req_path}"
        )

    raw = _load_json(exec_req_path)
    req = _coerce_execution_request(raw)

    # Final invariant check
    assert_execution_request_valid(req)
