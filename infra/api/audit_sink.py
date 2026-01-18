from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import Any, Dict


def _utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def emit_audit_event(event: Dict[str, Any]) -> None:
    """
    Emit a single audit event as JSONL.

    This function must NEVER raise in a way that
    flips deny -> allow semantics upstream.
    """
    try:
        payload = dict(event)
        payload.setdefault("recorded_at", _utc_now())
        line = json.dumps(payload, ensure_ascii=False)
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    except Exception as e:
        fallback = {
            "event": "audit_error",
            "outcome": "deny",
            "error": str(e),
            "recorded_at": _utc_now(),
        }
        sys.stderr.write(json.dumps(fallback) + "\n")
        sys.stderr.flush()
