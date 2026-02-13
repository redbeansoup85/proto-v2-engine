from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from core.C_action.queue_consumer import _load_json, _save_json


def _now_iso() -> str:
    # CI determinism lock (optional)
    # Enable with: METAOS_CI_DETERMINISTIC_ORCH_PAYLOAD=1
    if os.getenv("METAOS_CI_DETERMINISTIC_ORCH_PAYLOAD", "").strip().lower() in {"1","true","yes","y","on"}:
        return "1970-01-01T00:00:00Z"
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_inbox_payload_from_processed(processed_path: str) -> Dict[str, Any]:
    p = _load_json(processed_path)

    plan = p.get("plan") or {}
    channel = (plan.get("channel") or p.get("channel") or "unknown")
    plan_id = (plan.get("plan_id") or p.get("plan_id") or "unknown")

    payload: Dict[str, Any] = {
        "kind": "ORCH_INBOX_V1",
        "ts_iso": _now_iso(),
        "source": "queue_consumer",
        "channel": channel,
        "plan": plan,
        "meta": {
            "processed_artifact_path": processed_path,
            "receipt_path": plan.get("receipt_path") or p.get("receipt_path"),
            "action_executed": bool(p.get("action_executed", False)),
        },
    }
    return payload


def write_inbox_payload(processed_path: str, inbox_base_dir: str = "logs/orchestrator/inbox") -> str:
    payload = build_inbox_payload_from_processed(processed_path)
    channel = payload.get("channel") or "unknown"
    plan_id = (payload.get("plan") or {}).get("plan_id") or "unknown"

    out_path = os.path.join(inbox_base_dir, channel, f"{plan_id}.json")
    _save_json(out_path, payload)

    # processed artifact에 forward 상태를 best-effort로 업데이트(실패해도 무방)
    try:
        processed = _load_json(processed_path)
        ds = processed.get("delivery_status") or {}
        ds.update(
            {
                "forwarded_to_orchestrator": True,
                "forward_payload_path": out_path,
            }
        )
        processed["delivery_status"] = ds
        _save_json(processed_path, processed)
    except Exception:
        pass

    return out_path
