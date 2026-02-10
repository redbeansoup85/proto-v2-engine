from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def execute_paper_broker(exec_intent: dict[str, Any]) -> dict[str, Any]:
    if exec_intent.get("schema_version") != "internal_exec_intent.v1":
        raise RuntimeError("FAIL_CLOSED: bad internal exec intent schema")
    if exec_intent.get("mode") != "paper":
        raise RuntimeError("FAIL_CLOSED: paper broker accepts paper mode only")
    return {
        "status": "accepted",
        "broker": "paper",
        "exec_intent_id": exec_intent.get("exec_intent_id"),
        "ts": _utc_now_iso(),
    }


def execute_real_broker_stub(exec_intent: dict[str, Any]) -> dict[str, Any]:
    _ = exec_intent
    raise RuntimeError("FAIL_CLOSED: real broker is not implemented in this phase")
