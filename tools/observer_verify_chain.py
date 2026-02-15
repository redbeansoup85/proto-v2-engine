#!/usr/bin/env python3

import argparse
import json
import hashlib
from pathlib import Path


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _canonical_bytes(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-jsonl", required=True)
    ap.add_argument(
        "--event-kind",
        default=None,
        help="If set, fail-closed unless every line has this event_kind. If omitted, accept any event_kind.",
    )
    args = ap.parse_args()

    p = Path(args.audit_jsonl)
    if not p.is_file():
        raise ValueError(f"audit file not found: {p}")

    prev_hash_expected = None
    last_hash = None
    n = 0

    with p.open("r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            n += 1
            o = json.loads(ln)

            if o.get("schema") != "observer_event.v1":
                raise ValueError(f"line {n}: schema mismatch")

            ek = o.get("event_kind")
            if not isinstance(ek, str) or not ek:
                raise ValueError(f"line {n}: event_kind missing/invalid")

            if args.event_kind is not None and ek != args.event_kind:
                raise ValueError(f"line {n}: event_kind mismatch")

            chain = o.get("chain")
            if not isinstance(chain, dict):
                raise ValueError(f"line {n}: chain missing/invalid")

            prev = chain.get("prev_hash")
            h = chain.get("hash")

            if h is None or not isinstance(h, str) or not h:
                raise ValueError(f"line {n}: chain.hash missing/invalid")

            # prev_hash must match previous line hash (or None on first)
            if prev_hash_expected is None:
                if prev is not None:
                    raise ValueError(f"line {n}: prev_hash must be null on first line")
            else:
                if prev != prev_hash_expected:
                    raise ValueError(f"line {n}: prev_hash mismatch (expected {prev_hash_expected} got {prev})")

            # verify hash integrity: recompute with chain.hash=None
            o2 = json.loads(ln)
            o2["chain"]["hash"] = None
            h2 = _sha256_hex(_canonical_bytes(o2))
            if h2 != h:
                raise ValueError(f"line {n}: hash mismatch (computed {h2} stored {h})")

            prev_hash_expected = h
            last_hash = h

    if n == 0:
        raise ValueError("audit file has no records")

    print(f"OK: chain verified lines={n} tail_hash={last_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
