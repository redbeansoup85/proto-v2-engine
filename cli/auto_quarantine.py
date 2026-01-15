#!/usr/bin/env python3
"""
Auto Quarantine for HARD_FAIL runs
- scans exceptions in date range
- moves related context/card files into _quarantine
- writes fix helper with safe wording template
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

VAULT = Path("vault")

FORBIDDEN_HINT = "Context snapshot only. No directives."
FORBIDDEN_TERMS = [
    "recommend","buy","sell","target","entry","exit",
    "bullish","bearish","long","short","go long","go short"
]


def parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def daterange(start: datetime, end: datetime):
    d = start
    while d <= end:
        yield d.strftime("%Y/%m/%d")
        d = d.replace(day=d.day + 1)


def safe_json(p: Path) -> Optional[Dict]:
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser("auto_quarantine")
    ap.add_argument("--from", dest="from_", required=True)
    ap.add_argument("--to", required=True)
    args = ap.parse_args()

    start = parse_date(args.from_)
    end = parse_date(args.to)

    hits = 0

    for date_path in daterange(start, end):
        ex_dir = VAULT / "exceptions" / date_path
        if not ex_dir.exists():
            continue

        qdir = VAULT / "quarantine" / date_path
        qdir.mkdir(parents=True, exist_ok=True)

        for ex in ex_dir.glob("exception_*__*.json"):
            data = safe_json(ex)
            if not data:
                continue
            if str(data.get("severity")).upper() != "HARD_FAIL":
                continue

            hits += 1
            run_id = data.get("run_id")
            code = data.get("code")

            # move exception
            shutil.copy2(ex, qdir / ex.name)

            # write helper memo
            helper = {
                "run_id": run_id,
                "code": code,
                "fix_template": FORBIDDEN_HINT,
                "forbidden_terms": FORBIDDEN_TERMS,
                "action": "Edit context/card wording → rerun tlog → vscan --strict-context"
            }
            (qdir / f"fix_{run_id}.json").write_text(
                json.dumps(helper, indent=2)
            )

    print(f"🧯 auto_quarantine done | HARD_FAIL moved: {hits}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

