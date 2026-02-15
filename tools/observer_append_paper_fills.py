#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Append paper_fill_event.v1 into a single audit-chain stream (jsonl).
- Adds prev_hash + hash
- GENESIS supported
- Deterministic hashing: sha256(canonical_json(payload_without_hash_fields + prev_hash))
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


class ContractError(Exception):
    pass


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def require(cond: bool, msg: str) -> None:
    if not cond:
        raise ContractError(msg)

def is_iso_z(ts: str) -> bool:
    return isinstance(ts, str) and ts.endswith("Z") and "T" in ts

def validate_fill_event(doc: Dict[str, Any]) -> None:
    require(doc.get("schema") == "paper_fill_event.v1", "schema must be paper_fill_event.v1")
    require(doc.get("domain") == "SENTINEL", "domain must be SENTINEL")
    require(doc.get("kind") == "PAPER_FILL", "kind must be PAPER_FILL")
    require(isinstance(doc.get("event_id"), str) and doc["event_id"], "event_id required")
    require(is_iso_z(doc.get("ts_iso", "")), "ts_iso must be ISO-8601 Z")
    require(isinstance(doc.get("fills"), list) and len(doc["fills"]) > 0, "fills must be non-empty list")
    require(isinstance(doc.get("source"), dict) and isinstance(doc["source"].get("ref"), str), "source.ref required")


def read_last_hash(chain_path: str) -> Optional[str]:
    if not os.path.exists(chain_path):
        return None
    last = None
    with open(chain_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            last = line
    if last is None:
        return None
    try:
        obj = json.loads(last)
        h = obj.get("hash")
        if isinstance(h, str) and h:
            return h
        return None
    except Exception:
        return None


def compute_chain_hash(payload: Dict[str, Any], prev_hash: str) -> str:
    # hash over canonical payload (excluding hash fields) + prev_hash
    clean = dict(payload)
    clean.pop("hash", None)
    clean.pop("prev_hash", None)
    seed = {
        "prev_hash": prev_hash,
        "payload": clean,
    }
    return sha256_hex(_canonical_json(seed))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="paper_fill_event.v1 path")
    ap.add_argument("--chain", default="var/audit_chain/paper_fills.jsonl", help="audit chain jsonl path")
    ap.add_argument("--stamp-generated-at", action="store_true", help="stamp meta.generated_at_iso (non-deterministic)")
    args = ap.parse_args()

    try:
        doc = load_json(args.input)
        validate_fill_event(doc)

        prev = read_last_hash(args.chain)
        if prev is None:
            prev = "GENESIS"

        # optional wall-clock stamp (off by default)
        if args.stamp_generated_at:
            meta = doc.get("meta") if isinstance(doc.get("meta"), dict) else {}
            meta = dict(meta)
            meta["generated_at_iso"] = now_iso_utc()
            doc["meta"] = meta

        doc["prev_hash"] = prev
        doc["hash"] = compute_chain_hash(doc, prev)

        os.makedirs(os.path.dirname(args.chain), exist_ok=True)
        with open(args.chain, "a", encoding="utf-8") as f:
            f.write(_canonical_json(doc))
            f.write("\n")

        print(f"OK: appended to {args.chain}")
        print(f"hash={doc['hash']}")
        return 0

    except ContractError as e:
        print(f"CONTRACT_FAIL: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
