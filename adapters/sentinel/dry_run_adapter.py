#!/usr/bin/env python3
"""
Sentinel Dry-Run Adapter (Thin Slice v1)

- Input : sentinel_trade_intent.v1 (JSON)
- Output: sentinel_trade_decision.v1 (JSON)
- Behavior: deterministic, fail-closed, no external deps

Optional:
- If SENTINEL_OBSERVER_OUT is set, append a LOCK-3 compliant observer event.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from tools.observer.append_observer_event import append_observer_event


def _append_observer(intent_id: str, status: str) -> None:
    obs_out = os.getenv("SENTINEL_OBSERVER_OUT", "").strip()
    if not obs_out:
        return
    out_path = Path(obs_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    _iid = intent_id if isinstance(intent_id, str) and intent_id else "0000"
    append_observer_event(
        out_path=out_path,
        event_id=f"EVT-{_iid}",
        judgment_id=f"JDG-{_iid}",
        approval_record_id=f"APR-{_iid}",
        execution_run_id=f"RUN-{_iid}",
        status=status,          # must be one of: started/ok/fail
        latency_ms=1.0,         # allowed metric key
    )


def fail(msg: str, *, intent_id: str = "0000") -> None:
    # Record FAIL (best-effort; never block failure path)
    try:
        _append_observer(intent_id, "fail")
    except Exception:
        pass
    print(msg, file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        fail("EMPTY_INPUT", intent_id="0000")

    try:
        obj: Dict[str, Any] = json.loads(raw)
    except Exception:
        fail("INVALID_JSON", intent_id="0000")

    # Minimal fail-closed checks (schema gate is separate)
    if obj.get("schema") != "sentinel_trade_intent.v1":
        fail("SCHEMA_MISMATCH", intent_id=str(obj.get("intent_id") or "0000"))
    if obj.get("domain_id") != "sentinel.trade":
        fail("DOMAIN_ID_MISMATCH", intent_id=str(obj.get("intent_id") or "0000"))
    if obj.get("mode") != "DRY_RUN":
        fail("MODE_NOT_DRY_RUN", intent_id=str(obj.get("intent_id") or "0000"))

    intent_id = obj.get("intent_id", "")
    asset = obj.get("asset", "")
    side = obj.get("side", "")

    if not isinstance(intent_id, str) or len(intent_id) < 8:
        fail("BAD_INTENT_ID", intent_id="0000")
    if not isinstance(asset, str) or len(asset) < 2:
        fail("BAD_ASSET", intent_id=intent_id)
    if side not in ("LONG", "SHORT", "FLAT"):
        fail("BAD_SIDE", intent_id=intent_id)

    # Deterministic policy (placeholder): always allow dry-run
    out = {
        "schema": "sentinel_trade_decision.v1",
        "domain_id": "sentinel.trade",
        "intent_id": intent_id,
        "decision": "ALLOW_DRY_RUN",
        "reason": f"Dry-run accepted for {asset} {side}.",
        "risk_flags": [],
    }

    # Record OK (best-effort)
    try:
        _append_observer(intent_id, "ok")
    except Exception:
        pass

    sys.stdout.write(json.dumps(out, sort_keys=True))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
