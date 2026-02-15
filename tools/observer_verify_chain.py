#!/usr/bin/env python3

import argparse
import hashlib
import json
from pathlib import Path

GENESIS = "GENESIS"


def _canonical_bytes(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha256_hex(buf: bytes) -> str:
    return hashlib.sha256(buf).hexdigest()


def _extract_chain_fields(rec: dict, line_no: int) -> tuple[str | None, str, str]:
    """
    Support both layouts:
      A) nested: {"chain": {"prev_hash": "...", "hash": "..."}}
      B) top-level: {"prev_hash": "...", "hash": "..."}
    Returns (prev_hash, hash, layout).
    """
    if isinstance(rec.get("chain"), dict):
        ch = rec["chain"]
        prev = ch.get("prev_hash")
        h = ch.get("hash")
        layout = "nested"
    else:
        prev = rec.get("prev_hash")
        h = rec.get("hash")
        layout = "top"

    if not h or not isinstance(h, str):
        raise ValueError(f"line {line_no}: missing chain hash")
    if prev is not None and not isinstance(prev, str):
        raise ValueError(f"line {line_no}: prev_hash must be string or null")
    return prev, h, layout


def _is_first_prev_ok(prev_hash) -> bool:
    return prev_hash is None or prev_hash == GENESIS


def _preimage_for_hash(rec: dict, layout: str) -> bytes:
    copy_rec = json.loads(json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False))

    # Signature/auth metadata should never influence chain hash.
    copy_rec.pop("signature", None)
    copy_rec.pop("signature_meta", None)
    copy_rec.pop("auth", None)

    if layout == "nested":
        chain = copy_rec.get("chain")
        if not isinstance(chain, dict):
            raise ValueError("nested layout missing chain object")
        chain["hash"] = None
    else:
        copy_rec["hash"] = None

    return _canonical_bytes(copy_rec)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-jsonl", required=True)
    args = ap.parse_args()

    p = Path(args.audit_jsonl)
    if not p.exists():
        raise FileNotFoundError(str(p))

    lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        raise ValueError("empty audit file")

    last_hash = None
    first_prev = None

    for n, ln in enumerate(lines, start=1):
        try:
            row = json.loads(ln)
        except Exception as e:
            raise ValueError(f"line {n}: invalid json: {e}") from e

        prev, h, layout = _extract_chain_fields(row, n)

        if n == 1:
            if not _is_first_prev_ok(prev):
                raise ValueError(f"line {n}: prev_hash must be null or GENESIS on first line")
            first_prev = prev
        else:
            if prev != last_hash:
                raise ValueError(f"line {n}: prev_hash mismatch (expected {last_hash}, got {prev})")

        computed = _sha256_hex(_preimage_for_hash(row, layout))
        if computed != h:
            raise ValueError(f"line {n}: hash mismatch (computed {computed} stored {h})")

        last_hash = h

    print(f"OK: chain verified rows={len(lines)} head_prev={first_prev} tail_hash={last_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
