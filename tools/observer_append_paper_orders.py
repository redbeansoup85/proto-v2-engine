#!/usr/bin/env python3

import argparse
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone


def _canon(obj) -> bytes:
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_last_hash(audit_path: Path) -> str:
    if not audit_path.exists():
        return "GENESIS"

    last = None
    with audit_path.open("rb") as f:
        for line in f:
            last = line

    if not last:
        return "GENESIS"

    obj = json.loads(last.decode("utf-8"))
    return obj.get("hash", "GENESIS")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper-file", required=True)
    ap.add_argument("--audit-jsonl", required=True)
    args = ap.parse_args()

    paper_path = Path(args.paper_file)
    audit_path = Path(args.audit_jsonl)

    if not paper_path.is_file():
        raise ValueError(f"paper file not found: {paper_path}")

    audit_path.parent.mkdir(parents=True, exist_ok=True)

    paper = json.loads(paper_path.read_text(encoding="utf-8"))

    if paper.get("schema") != "paper_order_intent.v1":
        raise ValueError("schema mismatch (expected paper_order_intent.v1)")

    prev_hash = _read_last_hash(audit_path)

    event = {
        "schema": "audit.paper_orders.v1",
        "ts_iso": _now_iso(),
        "paper_event_id": paper.get("event_id"),
        "paper_ts": paper.get("intent", {}).get("ts"),
        "orders_count": len(paper.get("intent", {}).get("orders", [])),
        "policy_id": paper.get("meta", {}).get("policy_id"),
        "policy_sha256": paper.get("meta", {}).get("policy_sha256"),
        "evidence_ref": str(paper_path),
        "prev_hash": prev_hash,
    }

    h = _sha256_hex(_canon(event))
    event["hash"] = h

    with audit_path.open("ab") as f:
        f.write(_canon(event) + b"\n")

    print(
        f"OK: appended to {audit_path} "
        f"hash={h} prev={prev_hash} orders={event['orders_count']}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
