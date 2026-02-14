#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outbox-item", required=True)
    ap.add_argument("--ts", type=int, default=None)
    ap.add_argument("--event-id", default=None)
    args = ap.parse_args()

    p = Path(args.outbox_item)
    if not p.exists():
        print(f"FAIL-CLOSED: outbox item not found: {p}", file=sys.stderr)
        raise SystemExit(1)

    outbox = json.loads(p.read_text(encoding="utf-8"))

    evt = {
        "schema": "audit_event.v1",
        "kind": "ALERT_EMITTED",
        "event_id": args.event_id or f'alert_emitted:{outbox.get("channel","unknown")}:{outbox.get("plan_id","unknown")}',
        "payload": outbox,
    }
    if args.ts is not None:
        evt["ts"] = args.ts

    from auralis_v1.core.audit_chain import append_audit  # type: ignore
    rec = append_audit(evt)
    print(json.dumps(rec, ensure_ascii=False))

if __name__ == "__main__":
    main()
