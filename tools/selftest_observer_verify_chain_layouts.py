#!/usr/bin/env python3

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


def _write_jsonl(path: Path, rows: list[dict]):
    path.write_text("\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + "\n", encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)

        nested = td_path / "nested.jsonl"
        rows_nested = [
            {"schema": "observer_event.v1", "chain": {"prev_hash": "GENESIS", "hash": "aaa"}, "payload": {"x": 1}},
            {"schema": "observer_event.v1", "chain": {"prev_hash": "aaa", "hash": "bbb"}, "payload": {"x": 2}},
        ]
        _write_jsonl(nested, rows_nested)
        rc, out = _run_verify(nested)
        if rc != 0:
            raise SystemExit(f"FAIL: nested layout should pass\n{out}")

        top = td_path / "top.jsonl"
        rows_top = [
            {"schema": "audit.paper_orders.v1", "prev_hash": "GENESIS", "hash": "111", "orders_count": 2},
            {"schema": "audit.paper_orders.v1", "prev_hash": "111", "hash": "222", "orders_count": 3},
        ]
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

    print("SELFTEST_OK_VERIFY_CHAIN_LAYOUTS")


if __name__ == "__main__":
    main()
