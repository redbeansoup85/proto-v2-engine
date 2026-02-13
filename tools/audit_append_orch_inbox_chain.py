#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional


def _load_json(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", required=True, help="orch inbox payload json path")
    ap.add_argument("--ts", type=int, default=None, help="fixed ts for CI determinism (optional)")
    ap.add_argument("--event-id", dest="event_id", default=None, help="fixed event_id (optional)")
    args = ap.parse_args()

    inbox = _load_json(args.inbox)

    evt: Dict[str, Any] = {
        "schema": "audit_event.v1",
        "kind": "ORCH_INBOX_PAYLOAD",
        "event_id": args.event_id
        or f'orch_inbox:{inbox.get("channel","unknown")}:{(inbox.get("plan") or {}).get("plan_id","unknown")}',
        "payload": inbox,
    }
    if args.ts is not None:
        evt["ts"] = args.ts

    # auralis_v1 append_audit handles:
    # - auralis_genesis_hash
    # - prev_hash + hash chaining
    from auralis_v1.core.audit_chain import append_audit  # type: ignore

    rec = append_audit(evt)
    print(json.dumps(rec, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
