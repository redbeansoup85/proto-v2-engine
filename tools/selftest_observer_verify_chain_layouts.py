#!/usr/bin/env python3

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def _run_verify(path: Path) -> tuple[int, str]:
    cmd = [sys.executable, "tools/observer_verify_chain.py", "--audit-jsonl", str(path)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out.strip()


def _canonical_bytes(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha256_hex(buf: bytes) -> str:
    return hashlib.sha256(buf).hexdigest()


def _preimage_for_hash(rec: dict, layout: str) -> dict:
    copy_rec = json.loads(json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False))
    copy_rec.pop("signature", None)
    copy_rec.pop("signature_meta", None)
    copy_rec.pop("auth", None)
    if layout == "nested":
        chain = copy_rec.get("chain")
        if not isinstance(chain, dict):
            raise ValueError("nested layout missing chain")
        chain["hash"] = None
    else:
        copy_rec.pop("hash", None)
    return copy_rec


def _seal_nested_rows(seed_rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    prev = "GENESIS"
    for row in seed_rows:
        rec = json.loads(json.dumps(row, ensure_ascii=False, allow_nan=False))
        rec.setdefault("chain", {})
        rec["chain"]["prev_hash"] = prev
        rec["chain"]["hash"] = ""
        h = _sha256_hex(_canonical_bytes(_preimage_for_hash(rec, "nested")))
        rec["chain"]["hash"] = h
        out.append(rec)
        prev = h
    return out


def _seal_top_rows(seed_rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    prev = "GENESIS"
    for row in seed_rows:
        rec = json.loads(json.dumps(row, ensure_ascii=False, allow_nan=False))
        rec["prev_hash"] = prev
        rec["hash"] = ""
        h = _sha256_hex(_canonical_bytes(_preimage_for_hash(rec, "top")))
        rec["hash"] = h
        out.append(rec)
        prev = h
    return out


def _write_jsonl(path: Path, rows: list[dict]):
    path.write_text("\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + "\n", encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)

        nested = td_path / "nested.jsonl"
        rows_nested = _seal_nested_rows(
            [
                {"schema": "observer_event.v1", "event_kind": "execution_intent", "chain": {}, "payload": {"x": 1}},
                {"schema": "observer_event.v1", "event_kind": "execution_intent", "chain": {}, "payload": {"x": 2}},
            ]
        )
        _write_jsonl(nested, rows_nested)
        rc, out = _run_verify(nested)
        if rc != 0:
            raise SystemExit(f"FAIL: nested layout should pass\n{out}")

        top = td_path / "top.jsonl"
        rows_top = _seal_top_rows(
            [
                {"schema": "audit.paper_orders.v1", "orders_count": 2},
                {"schema": "audit.paper_orders.v1", "orders_count": 3},
            ]
        )
        _write_jsonl(top, rows_top)
        rc, out = _run_verify(top)
        if rc != 0:
            raise SystemExit(f"FAIL: top-level layout should pass\n{out}")

        bad = td_path / "bad.jsonl"
        rows_bad = [
            {"schema": "observer_event.v1", "event_kind": "execution_intent", "chain": {"prev_hash": "NOT_ALLOWED", "hash": "xxx"}},
        ]
        _write_jsonl(bad, rows_bad)
        rc, _ = _run_verify(bad)
        if rc == 0:
            raise SystemExit("FAIL: bad first prev_hash should fail but passed")

    print("SELFTEST_OK_VERIFY_CHAIN_LAYOUTS")


if __name__ == "__main__":
    main()
