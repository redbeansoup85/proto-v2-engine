#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from auralis_v1.core.audit_chain import append_audit


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--processed", required=True, help="Path to processed artifact JSON")
    ap.add_argument("--ts", required=True, type=int)
    ap.add_argument("--event-id", required=True)
    args = ap.parse_args()

    processed_path = str(Path(args.processed))

    evt = {
        "schema": "audit_event.v1",
        "kind": "QUEUE_PROCESSED",
        "event_id": args.event_id,
        "ts": args.ts,
        "payload": {
            "processed_path": processed_path,
        },
    }
    append_audit(evt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
