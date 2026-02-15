#!/usr/bin/env python3

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--intent-file", required=True)
    ap.add_argument("--audit-jsonl", required=True)
    args = ap.parse_args()

    intent_path = Path(args.intent_file)
    audit_path = Path(args.audit_jsonl)

    if not intent_path.is_file():
        raise ValueError(f"intent file not found: {intent_path}")

    audit_path.parent.mkdir(parents=True, exist_ok=True)

    intent = json.loads(intent_path.read_text(encoding="utf-8"))

    # minimal envelope discipline
    record = {
        "schema": "observer_event.v1",
        "event_kind": "execution_intent",
        "ts_append_iso": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "payload": intent,
    }

    with audit_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"OK: appended to {audit_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
