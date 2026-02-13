#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path

COMPARE_KEYS = [
    "schema",
    "policy_sha256",
    "policy_capsule_digest",
    "gate_same_digest",
    "plan_digest",
    "queue_digest",
    "processed_digest",
    "orch_inbox_digest",
    "orch_decision_digest",
    "outbox_item_digest",
]

def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def main() -> int:
    if len(sys.argv) != 3:
        print("usage: verify_lock_report.py <expected_json> <current_json>", file=sys.stderr)
        return 2

    expected = _load(Path(sys.argv[1]))
    current = _load(Path(sys.argv[2]))

    mismatches = []
    for k in COMPARE_KEYS:
        if expected.get(k) != current.get(k):
            mismatches.append((k, expected.get(k), current.get(k)))

    if mismatches:
        print("FAIL-CLOSED: lock report mismatch")
        for k, ev, cv in mismatches:
            print(f"- {k}: expected={ev} current={cv}")
        return 1

    print("OK: lock report matches expected snapshot")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
