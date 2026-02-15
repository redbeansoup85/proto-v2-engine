#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from nacl.signing import VerifyKey
except Exception as e:
    print(json.dumps({"error": "SIG_DEPENDENCY_MISSING", "detail": str(e)}), file=sys.stderr)
    raise SystemExit(2)


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


def _extract_hash_hex(obj: Dict[str, Any]) -> Optional[str]:
    chain = obj.get("chain")
    if isinstance(chain, dict):
        h = chain.get("hash")
        if isinstance(h, str) and h.strip():
            return h.strip()
    h2 = obj.get("hash")
    if isinstance(h2, str) and h2.strip():
        return h2.strip()
    return None


def _extract_sig_hex(obj: Dict[str, Any]) -> Optional[str]:
    sig = obj.get("signature")
    if sig is None:
        return None
    if isinstance(sig, str) and sig.strip():
        return sig.strip()
    if isinstance(sig, dict):
        s = sig.get("signature")
        if isinstance(s, str) and s.strip():
            return s.strip()
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify ed25519 signatures for observer event JSONL (nested/top layout).")
    ap.add_argument("--path", required=True)
    ap.add_argument("--pub", required=True, help="Public key path (32 bytes raw, nacl verify key)")
    args = ap.parse_args()

    sig_required = os.getenv("SIG_REQUIRED", "0") == "1"

    pub_path = Path(args.pub).expanduser()
    if not pub_path.exists():
        _fail("PUBKEY_NOT_FOUND", str(pub_path))

    vk = VerifyKey(pub_path.read_bytes())
    lines = _load_lines(Path(args.path))

    for idx, line in enumerate(lines, start=1):
        try:
            obj = json.loads(line)
        except Exception:
            _fail("BAD_JSON", f"line={idx}")

        h = _extract_hash_hex(obj)
        if not h:
            _fail("BAD_HASH", f"line={idx}")

        sig_hex = _extract_sig_hex(obj)
        if not sig_hex:
            if sig_required:
                _fail("MISSING_SIGNATURE", f"line={idx}")
            continue

        try:
            vk.verify(bytes.fromhex(h), bytes.fromhex(sig_hex))
        except Exception as e:
            _fail("SIGNATURE_VERIFY_FAIL", f"line={idx} err={e}")

    print(f"OK: signatures verified lines={len(lines)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
