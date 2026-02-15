#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    from nacl.signing import VerifyKey
except Exception as e:
    print(json.dumps({"error": "SIG_DEPENDENCY_MISSING", "detail": str(e)}), file=sys.stderr)
    raise SystemExit(2)

RE_HASH = re.compile(r"^[0-9a-f]{64}$")

def _fail(code: str, detail: str = "") -> None:
    print(json.dumps({"error": code, "detail": detail}, sort_keys=True), file=sys.stderr)
    raise SystemExit(2)

def _load_lines(path: Path) -> list[str]:
    if not path.exists():
        _fail("FILE_NOT_FOUND", str(path))
    txt = path.read_text(encoding="utf-8")
    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    if not lines:
        _fail("EMPTY_LOG", str(path))
    return lines

def main() -> int:
    ap = argparse.ArgumentParser(description="Verify ed25519 signatures for judgment_event.v1 JSONL.")
    ap.add_argument("--path", required=True)
    ap.add_argument("--pub", required=True, help="Public key path (32 bytes raw, nacl verify key)")
    args = ap.parse_args()

    sig_required = os.getenv("SIG_REQUIRED", "0") == "1"

    pub_path = Path(args.pub)
    if not pub_path.exists():
        _fail("PUBKEY_NOT_FOUND", str(pub_path))

    vk = VerifyKey(pub_path.read_bytes())
    lines = _load_lines(Path(args.path))

    for idx, line in enumerate(lines, start=1):
        try:
            obj = json.loads(line)
        except Exception:
            _fail("BAD_JSON", f"line={idx}")

        h = obj.get("hash")
        if not isinstance(h, str) or not RE_HASH.match(h):
            _fail("BAD_HASH", f"line={idx}")

        auth = obj.get("auth")
        if not auth:
            if sig_required:
                _fail("MISSING_AUTH", f"line={idx}")
            continue

        sig_hex = auth.get("signature")
        if not isinstance(sig_hex, str) or not sig_hex:
            _fail("BAD_SIGNATURE", f"line={idx}")

        try:
            vk.verify(bytes.fromhex(h), bytes.fromhex(sig_hex))
        except Exception as e:
            _fail("SIGNATURE_VERIFY_FAIL", f"line={idx} err={e}")

    print(f"OK: signatures verified lines={len(lines)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
