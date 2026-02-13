#!/usr/bin/env python3
from __future__ import annotations
import json, re, sys
from pathlib import Path

HEX64 = r"[0-9a-f]{64}"

def _first(text: str, pattern: str) -> str:
    m = re.search(pattern, text, re.M)
    return m.group(1) if m else "n/a"

def _block_digest(text: str, header: str) -> str:
    pat = rf"^\[CI\]\s+{re.escape(header)}\s*$.*?(?=^\[CI\]|\Z)"
    m = re.search(pat, text, re.M | re.S)
    if not m:
        return "n/a"
    block = m.group(0)
    m2 = re.search(rf"^digest1 = ({HEX64})$", block, re.M)
    return m2.group(1) if m2 else "n/a"

def main() -> int:
    if len(sys.argv) != 3:
        print("usage: build_lock_report.py <ci_log_txt> <out_json>", file=sys.stderr)
        return 2

    log_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    t = log_path.read_text(encoding="utf-8", errors="ignore")

    report = {
        "schema": "metaos_lock_report.v1",
        "ts_iso": "1970-01-01T00:00:00Z",
        "policy_sha256": _first(t, rf"^A\.policy_sha256 = ({HEX64})$"),
        "policy_capsule_digest": _first(t, rf"^A\.policy_capsule\.digest = ({HEX64})$"),
        "gate_same_digest": _first(t, rf"^same1\.digest = ({HEX64})$"),
        "plan_digest": _first(t, rf"^plan\.digest\.1 = ({HEX64})$"),
        "queue_digest": _first(t, rf"^queue\.digest\.1 = ({HEX64})$"),
        "processed_digest": _block_digest(t, "LOCK5 consumer+audit determinism"),
        "orch_inbox_digest": _block_digest(t, "LOCK6 orch inbox+audit determinism"),
        "orch_decision_digest": _block_digest(t, "LOCK7 orch decision+audit determinism"),
        "outbox_item_digest": _block_digest(t, "LOCK8 orch outbox+audit determinism"),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"OK: wrote {out_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
