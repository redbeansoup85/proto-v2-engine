#!/usr/bin/env python3
"""
Sentinel Trade Intent Schema Gate (stdlib-only, fail-closed, PASS-THROUGH)

- Reads ONE JSON object from stdin or --path
- Validates sentinel_trade_intent.v1 (MVP)
- On PASS: re-emits the ORIGINAL JSON to stdout (so pipelines work)
- On FAIL: prints {"error":..., "detail":...} to stderr and exits 2
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict

ALLOWED_SIDE = {"LONG", "SHORT", "FLAT"}
RE_ASSET = re.compile(r"^[A-Z0-9]{3,12}$")
RE_INTENT_ID = re.compile(r"^INTENT-[A-Za-z0-9_-]{8,}$")

REQUIRED_KEYS = ["schema", "domain_id", "intent_id", "mode", "asset", "side", "notes"]
ALLOWED_KEYS = set(REQUIRED_KEYS)

MAX_INPUT_BYTES = 512_000


def _fail(code: str, detail: str = "") -> None:
    print(json.dumps({"error": code, "detail": detail}, sort_keys=True), file=sys.stderr)
    raise SystemExit(2)


def _read_bytes_from_stdin() -> bytes:
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        _fail("INPUT_TOO_LARGE", f">{MAX_INPUT_BYTES} bytes")
    return raw


def _read_bytes_from_path(p: Path) -> bytes:
    if not p.exists():
        _fail("FILE_NOT_FOUND", str(p))
    data = p.read_bytes()
    if len(data) > MAX_INPUT_BYTES:
        _fail("INPUT_TOO_LARGE", f">{MAX_INPUT_BYTES} bytes: {p}")
    return data


def _load_json(raw: bytes) -> Dict[str, Any]:
    txt = raw.decode("utf-8", errors="replace").strip()
    if not txt:
        _fail("EMPTY_INPUT")
    try:
        obj = json.loads(txt)
    except Exception:
        _fail("BAD_JSON", txt[:800])
    if not isinstance(obj, dict):
        _fail("JSON_NOT_OBJECT", type(obj).__name__)
    return obj


def _validate(obj: Dict[str, Any]) -> None:
    extra = [k for k in obj.keys() if k not in ALLOWED_KEYS]
    if extra:
        _fail("UNEXPECTED_KEYS", ",".join(sorted(extra)))

    for k in REQUIRED_KEYS:
        if k not in obj:
            _fail("MISSING_KEY", k)

    if obj.get("schema") != "sentinel_trade_intent.v1":
        _fail("SCHEMA_MISMATCH", str(obj.get("schema")))
    if obj.get("domain_id") != "sentinel.trade":
        _fail("DOMAIN_MISMATCH", str(obj.get("domain_id")))
    if obj.get("mode") != "DRY_RUN":
        _fail("MODE_NOT_DRY_RUN", str(obj.get("mode")))

    if not isinstance(obj.get("intent_id"), str) or not RE_INTENT_ID.match(obj["intent_id"]):
        _fail("BAD_INTENT_ID", str(obj.get("intent_id")))

    if not isinstance(obj.get("asset"), str) or not RE_ASSET.match(obj["asset"]):
        _fail("BAD_ASSET", str(obj.get("asset")))

    if obj.get("side") not in ALLOWED_SIDE:
        _fail("BAD_SIDE", str(obj.get("side")))

    if not isinstance(obj.get("notes"), str) or len(obj["notes"].strip()) < 1:
        _fail("BAD_NOTES", str(obj.get("notes")))


def main() -> int:
    ap = argparse.ArgumentParser(description="Pass-through schema gate for sentinel_trade_intent.v1 (MVP).")
    ap.add_argument("--path", default="", help="Read JSON from file (default: stdin)")
    args = ap.parse_args()

    raw = _read_bytes_from_path(Path(args.path)) if args.path else _read_bytes_from_stdin()
    obj = _load_json(raw)
    _validate(obj)

    # PASS-THROUGH: re-emit validated object for downstream pipeline stages
    sys.stdout.write(json.dumps(obj, sort_keys=True, separators=(",", ":")))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
