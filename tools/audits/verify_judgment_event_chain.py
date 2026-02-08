#!/usr/bin/env python3
"""
Verify hash-chained judgment_event.v1 JSONL (fail-closed, stdlib-only)

Rules:
- Each line must be a JSON object with:
  schema=judgment_event.v1, prev_hash, hash
- hash must equal sha256(canonical_json(event_without_hash))
- prev_hash must equal previous line's hash (or GENESIS for first)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict

GENESIS_HASH = "0" * 64
RE_HASH = re.compile(r"^[0-9a-f]{64}$")


def _fail(code: str, detail: str = "") -> None:
    print(json.dumps({"error": code, "detail": detail}, sort_keys=True), file=sys.stderr)
    raise SystemExit(2)


def _canonical_json(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _load_lines(path: Path) -> list[str]:
    if not path.exists():
        _fail("FILE_NOT_FOUND", str(path))
    txt = path.read_text(encoding="utf-8")
    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    if not lines:
        _fail("EMPTY_LOG", str(path))
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify judgment_event.v1 hash chain JSONL (fail-closed).")
    ap.add_argument("--path", default="audits/sentinel/judgment_events_chain.jsonl")
    args = ap.parse_args()

    path = Path(args.path)
    lines = _load_lines(path)

    prev = GENESIS_HASH
    for idx, line in enumerate(lines, start=1):
        try:
            obj = json.loads(line)
        except Exception:
            _fail("BAD_JSON", f"line={idx}")

        if not isinstance(obj, dict):
            _fail("NOT_OBJECT", f"line={idx}")

        if obj.get("schema") != "judgment_event.v1":
            _fail("SCHEMA_MISMATCH", f"line={idx} schema={obj.get('schema')}")

        ph = obj.get("prev_hash")
        h = obj.get("hash")
        if not isinstance(ph, str) or not RE_HASH.match(ph) and ph != GENESIS_HASH:
            _fail("BAD_PREV_HASH", f"line={idx}")
        if not isinstance(h, str) or not RE_HASH.match(h):
            _fail("BAD_HASH", f"line={idx}")

        if ph != prev:
            _fail("CHAIN_BREAK", f"line={idx} expected_prev={prev} got_prev={ph}")

        # recompute expected hash
        core = dict(obj)
        core.pop("hash", None)
        expected = _sha256_hex(_canonical_json(core))
        if expected != h:
            _fail("HASH_MISMATCH", f"line={idx}")

        prev = h

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
