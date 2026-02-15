#!/usr/bin/env python3
"""
Verify ed25519 signatures in judgment_event.v1 JSONL (fail-closed)

Notes:
- This tool only verifies signatures on record["hash"].
- It does not recompute or verify hash-chain integrity.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

RE_HASH = re.compile(r"^[0-9a-f]{64}$")


def _fail(code: str, detail: str = "") -> None:
    print(json.dumps({"error": code, "detail": detail}, sort_keys=True), file=sys.stderr)
    raise SystemExit(2)


def _load_pubkey(path: Path) -> bytes:
    if not path.exists():
        _fail("PUBKEY_NOT_FOUND", str(path))
    try:
        txt = path.read_text(encoding="utf-8").strip()
        return bytes.fromhex(txt)
    except Exception:
        _fail("PUBKEY_INVALID", str(path))


def _load_lines(path: Path) -> list[str]:
    if not path.exists():
        _fail("FILE_NOT_FOUND", str(path))
    txt = path.read_text(encoding="utf-8")
    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    if not lines:
        _fail("EMPTY_LOG", str(path))
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify judgment_event.v1 signatures (ed25519).")
    ap.add_argument("--path", default="audits/sentinel/judgment_events_chain.jsonl")
    ap.add_argument("--pub", required=True)
    args = ap.parse_args()

    try:
        from nacl.signing import VerifyKey
    except Exception as exc:
        _fail("SIG_DEPENDENCY_MISSING", str(exc))

    sig_required = str(os.getenv("SIG_REQUIRED", "0")).strip() == "1"
    verify_key = VerifyKey(_load_pubkey(Path(args.pub)))
    lines = _load_lines(Path(args.path))

    for idx, line in enumerate(lines, start=1):
        try:
            obj = json.loads(line)
        except Exception:
            _fail("BAD_JSON", f"line={idx}")
        if not isinstance(obj, dict):
            _fail("NOT_OBJECT", f"line={idx}")

        hash_hex = obj.get("hash")
        if not isinstance(hash_hex, str) or not RE_HASH.match(hash_hex):
            _fail("BAD_HASH", f"line={idx}")

        auth = obj.get("auth")
        if auth is None:
            if sig_required:
                _fail("SIG_REQUIRED_MISSING", f"line={idx}")
            continue

        if not isinstance(auth, dict):
            _fail("BAD_AUTH", f"line={idx}")
        if auth.get("algorithm") != "ed25519":
            _fail("SIG_ALG_UNSUPPORTED", f"line={idx}")
        if auth.get("signed_digest") != "hash":
            _fail("SIG_DIGEST_MISMATCH", f"line={idx}")

        signature_hex = auth.get("signature")
        if not isinstance(signature_hex, str):
            _fail("SIG_MISSING", f"line={idx}")
        try:
            signature = bytes.fromhex(signature_hex)
            payload = bytes.fromhex(hash_hex)
        except ValueError:
            _fail("SIG_BAD_HEX", f"line={idx}")

        try:
            verify_key.verify(payload, signature)
        except Exception:
            _fail("SIG_INVALID", f"line={idx}")

    print(f"OK: signatures verified lines={len(lines)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
