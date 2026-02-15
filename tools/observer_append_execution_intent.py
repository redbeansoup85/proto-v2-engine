#!/usr/bin/env python3

import argparse
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def _canonical_bytes(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def _read_last_hash(audit_path: Path) -> str | None:
    if not audit_path.is_file():
        return None
    with audit_path.open("rb") as f:
        f.seek(0, 2)
        end = f.tell()
        if end == 0:
            return None
        size = min(8192, end)
        f.seek(end - size)
        chunk = f.read(size)

    lines = [ln for ln in chunk.splitlines() if ln.strip()]
    if not lines:
        return None
    try:
        last = json.loads(lines[-1].decode("utf-8"))
        return last.get("chain", {}).get("hash")
    except Exception:
        return None

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
    prev_hash = _read_last_hash(audit_path)

    record = {
        "schema": "observer_event.v1",
        "event_kind": "execution_intent",
        "ts_append_iso": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "payload": intent,
        "chain": {
            "prev_hash": prev_hash,
            "hash": None,  # filled below
        },
    }

    h = _sha256_hex(_canonical_bytes(record))
    record["chain"]["hash"] = h

    with audit_path.open("ab") as f:
        f.write(_canonical_bytes(record) + b"\n")

    print(f"OK: appended to {audit_path} hash={h} prev={prev_hash}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
