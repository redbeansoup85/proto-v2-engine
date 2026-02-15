#!/usr/bin/env python3

import json
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path


def _run_verify(path: Path) -> tuple[int, str]:
    cmd = [sys.executable, "tools/observer_verify_chain.py", "--audit-jsonl", str(path)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out.strip()


def _write_jsonl(path: Path, rows: list[dict]):
    path.write_text("\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + "\n", encoding="utf-8")


def _canonical_bytes(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _hash_row(row: dict, nested: bool) -> str:
    rec = json.loads(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False))
    rec.pop("signature", None)
    rec.pop("signature_meta", None)
    rec.pop("auth", None)
    if nested:
        rec["chain"]["hash"] = None
    else:
        rec["hash"] = None
    return hashlib.sha256(_canonical_bytes(rec)).hexdigest()


def _tamper_hex_char(h: str) -> str:
    if not h:
        return h
    return ("0" if h[0] != "0" else "1") + h[1:]


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)

        nested = td_path / "nested.jsonl"
        rows_nested = [
            {"schema": "observer_event.v1", "chain": {"prev_hash": "GENESIS", "hash": None}, "payload": {"x": 1}},
            {"schema": "observer_event.v1", "chain": {"prev_hash": None, "hash": None}, "payload": {"x": 2}},
        ]
        rows_nested[0]["chain"]["hash"] = _hash_row(rows_nested[0], nested=True)
        rows_nested[1]["chain"]["prev_hash"] = rows_nested[0]["chain"]["hash"]
        rows_nested[1]["chain"]["hash"] = _hash_row(rows_nested[1], nested=True)
        _write_jsonl(nested, rows_nested)
        rc, out = _run_verify(nested)
        if rc != 0:
            raise SystemExit(f"FAIL: nested layout should pass\n{out}")

        top = td_path / "top.jsonl"
        rows_top = [
            {"schema": "audit.paper_orders.v1", "prev_hash": "GENESIS", "hash": None, "orders_count": 2},
            {"schema": "audit.paper_orders.v1", "prev_hash": None, "hash": None, "orders_count": 3},
        ]
        rows_top[0]["hash"] = _hash_row(rows_top[0], nested=False)
        rows_top[1]["prev_hash"] = rows_top[0]["hash"]
        rows_top[1]["hash"] = _hash_row(rows_top[1], nested=False)
        _write_jsonl(top, rows_top)
        rc, out = _run_verify(top)
        if rc != 0:
            raise SystemExit(f"FAIL: top-level layout should pass\n{out}")

        bad = td_path / "bad.jsonl"
        rows_bad = [
            {"schema": "observer_event.v1", "chain": {"prev_hash": "NOT_ALLOWED", "hash": "xxx"}},
        ]
        _write_jsonl(bad, rows_bad)
        rc, _ = _run_verify(bad)
        if rc == 0:
            raise SystemExit("FAIL: bad first prev_hash should fail but passed")

        tampered = td_path / "tampered.jsonl"
        rows_tampered = json.loads(json.dumps(rows_top))
        rows_tampered[1]["hash"] = _tamper_hex_char(rows_tampered[1]["hash"])
        _write_jsonl(tampered, rows_tampered)
        rc, _ = _run_verify(tampered)
        if rc == 0:
            raise SystemExit("FAIL: tampered hash should fail but passed")

    print("SELFTEST_OK_VERIFY_CHAIN_LAYOUTS")


if __name__ == "__main__":
    main()
