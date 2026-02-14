#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict


def _load_json(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _canonical_json(obj: Any) -> str:
    # must match chain_hasher canonicalization style
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", required=True, help="gate json path")
    ap.add_argument("--ts", type=int, default=None, help="fixed ts for CI determinism (optional)")
    ap.add_argument("--event-id", dest="event_id", default=None, help="fixed event_id (optional)")
    args = ap.parse_args()

    gate_path = str(Path(args.gate))
    d = _load_json(gate_path)

    channel = d.get("channel", "unknown")
    plan_id = d.get("plan_id", "unknown")

    ts = int(args.ts) if args.ts is not None else int(time.time())

    # Deterministic payload: store reference + digest, not the full gate json
    gate_digest = _sha256_hex(_canonical_json(d))

    evt: Dict[str, Any] = {
        "schema": "audit_event.v1",
        "kind": "GATE_DECISION",
        "event_id": args.event_id or f"orch_gate:{channel}:{plan_id}",
        "ts": ts,
        "payload": {
            "gate_path": gate_path,
            "gate_digest": gate_digest,
            "channel": channel,
            "plan_id": plan_id,
        },
    }

    from auralis_v1.core.audit_chain import append_audit  # type: ignore

    rec = append_audit(evt)
    print(json.dumps(rec, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
