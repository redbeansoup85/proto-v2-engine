#!/usr/bin/env python3
"""
Record outcome for a given judgment_id (stdlib-only, fail-closed)

- Writes audits/sentinel/outcomes/<JUDGMENT_ID>.json
- Does NOT modify judgment_event chain (immutable)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

OUT_DIR = Path("audits/sentinel/outcomes")

def _fail(code: str, detail: str="") -> None:
    print(json.dumps({"error": code, "detail": detail}, sort_keys=True), file=sys.stderr)
    raise SystemExit(2)

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def _canon(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))

def main() -> int:
    ap = argparse.ArgumentParser(description="Write outcome_record.v1 for a judgment_id.")
    ap.add_argument("--judgment-id", required=True)
    ap.add_argument("--label", choices=["WIN", "LOSS", "BE", "UNKNOWN"], default="UNKNOWN")
    ap.add_argument("--pnl_r", default="n/a", help="R multiple (number or n/a)")
    ap.add_argument("--pnl_pct", default="n/a", help="percent pnl (number or n/a)")
    ap.add_argument("--mae_pct", default="n/a", help="max adverse excursion % (number or n/a)")
    ap.add_argument("--mfe_pct", default="n/a", help="max favorable excursion % (number or n/a)")
    ap.add_argument("--exit_ts_utc", default="n/a")
    ap.add_argument("--notes", default="")
    args = ap.parse_args()

    jid = args.judgment_id.strip()
    if not jid:
        _fail("BAD_JUDGMENT_ID")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{jid}.json"

    rec: Dict[str, Any] = {
        "schema": "outcome_record.v1",
        "judgment_id": jid,
        "ts_recorded_utc": _utc_now_iso(),
        "label": args.label,
        "pnl_r": args.pnl_r,
        "pnl_pct": args.pnl_pct,
        "mae_pct": args.mae_pct,
        "mfe_pct": args.mfe_pct,
        "exit_ts_utc": args.exit_ts_utc,
        "notes": args.notes,
    }

    try:
        path.write_text(_canon(rec) + "\n", encoding="utf-8")
    except Exception as e:
        _fail("WRITE_FAIL", str(e))

    sys.stdout.write(_canon({"ok": True, "path": str(path)}) + "\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
