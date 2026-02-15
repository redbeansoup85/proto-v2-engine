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
    args = ap.parse_args()

    p = Path(args.audit_jsonl)
    if not p.is_file():
        raise ValueError(f"audit file not found: {p}")

    prev = None
    n = 0

    with p.open("rb") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            n += 1
            obj = json.loads(raw.decode("utf-8"))

            if obj.get("schema") != "observer_event.v1":
                raise ValueError(f"line {n}: schema mismatch")
            if obj.get("event_kind") != "execution_intent":
                raise ValueError(f"line {n}: event_kind mismatch")

            chain = obj.get("chain", {})
            if not isinstance(chain, dict):
                raise ValueError(f"line {n}: chain missing")

            ph = chain.get("prev_hash")
            h = chain.get("hash")
            if not isinstance(h, str) or not h:
                raise ValueError(f"line {n}: chain.hash missing")

            if n == 1:
                if ph is not None:
                    raise ValueError(f"line {n}: prev_hash must be None for first record")
            else:
                if ph != prev:
                    raise ValueError(f"line {n}: prev_hash mismatch expected={prev} got={ph}")

            core = dict(obj)
            core["chain"] = dict(chain)
            core["chain"]["hash"] = None
            recomputed = _sha256_hex(_canonical_bytes(core))
            if recomputed != h:
                raise ValueError(f"line {n}: hash mismatch expected={recomputed} got={h}")

            prev = h

    print(f"OK: chain verified lines={n} tail_hash={prev}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
