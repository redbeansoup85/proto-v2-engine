#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def _load_json(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outbox-item", required=True, help="orch outbox item json path")
    ap.add_argument("--ts", type=int, default=None, help="fixed ts for CI determinism (optional)")
    ap.add_argument("--event-id", dest="event_id", default=None, help="fixed event_id (optional)")
    args = ap.parse_args()

    item = _load_json(args.outbox_item)

    channel = item.get("channel", "unknown")
    plan_id = item.get("plan_id", "unknown")
    idx = item.get("index", "n/a")

    evt: Dict[str, Any] = {
        "schema": "audit_event.v1",
        "kind": "ORCH_OUTBOX_ITEM",
        "event_id": args.event_id or f"orch_outbox:{channel}:{plan_id}:{idx}",
        "payload": item,
    }
    if args.ts is not None:
        evt["ts"] = args.ts

    from auralis_v1.core.audit_chain import append_audit  # type: ignore
    rec = append_audit(evt)
    print(json.dumps(rec, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
