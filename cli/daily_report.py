#!/usr/bin/env python3
"""
Daily report for Trading OS Vault
- reads: vault/manifests/runs_index.jsonl
- joins: executions/, outcomes/, exceptions/
- prints: summary + top reasons + fails
- default: EXCLUDE quarantined runs (paths containing /quarantine/ or /_quarantine/)
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

VAULT_ROOT = Path("vault")
RUNS_INDEX = VAULT_ROOT / "manifests" / "runs_index.jsonl"


def utc_today_ymd() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def ymd_to_slash(ymd: str) -> str:
    # "2025-12-22" -> "2025/12/22"
    return ymd.replace("-", "/")


def safe_read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def parse_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def is_quarantined_path(p: str) -> bool:
    return ("/quarantine/" in p) or ("/_quarantine/" in p)


def load_exception_for_run(date_path: str, run_id: str) -> Optional[Dict[str, Any]]:
    ex_dir = VAULT_ROOT / "exceptions" / date_path
    if not ex_dir.exists():
        return None
    # match: exception_<RUN_ID>__*.json
    for p in sorted(ex_dir.glob(f"exception_{run_id}__*.json")):
        data = safe_read_json(p)
        if data:
            data["_path"] = str(p)
            return data
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Daily report from Vault")
    ap.add_argument("--date", default=utc_today_ymd(), help="UTC date: YYYY-MM-DD (default: today UTC)")
    ap.add_argument(
        "--include-quarantine",
        action="store_true",
        help="Include quarantined runs (paths containing /quarantine/ or /_quarantine/)",
    )
    args = ap.parse_args()

    date_ymd = args.date
    date_path = ymd_to_slash(date_ymd)

    rows = parse_jsonl(RUNS_INDEX)

    # Filter runs by date AND dedupe by run_id (keep last occurrence)
    last_by_run: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        exec_path = str(r.get("exec_path", "") or "")
        if f"/executions/{date_path}/" not in exec_path:
            continue

        # default exclude quarantine
        if (not args.include_quarantine) and is_quarantined_path(exec_path):
            continue

        run_id = r.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            continue
        # keep last (later lines overwrite)
        last_by_run[run_id] = r

    day_rows = list(last_by_run.values())

    # Aggregate
    total = len(day_rows)
    win = loss = be = cancel = open_ = 0
    net_pnl = 0.0
    pnl_ccy = None

    mae_sum = 0.0
    mfe_sum = 0.0
    mae_n = 0

    reasons: Dict[str, int] = {}
    hard_fails: List[Tuple[str, str, str]] = []  # (run_id, code, path)
    per_run_lines: List[str] = []

    for r in day_rows:
        run_id = r.get("run_id", "n/a")
        out_path = str(r.get("outcome_path", "") or "")
        outcome = safe_read_json(Path(out_path)) if out_path else None

        result = "UNKNOWN"
        reason = ""
        realized = 0.0
        ccy = None
        mae = None
        mfe = None

        if outcome:
            labels = outcome.get("labels", {}) or {}
            result = str(labels.get("result", "UNKNOWN"))
            reason = str(labels.get("reason", ""))

            pnl = outcome.get("pnl", {}) or {}
            realized = float(pnl.get("realized", 0.0) or 0.0)
            ccy = pnl.get("ccy", None) or pnl.get("currency", None)

            ex = outcome.get("excursions", {}) or {}
            mae = ex.get("mae", None)
            mfe = ex.get("mfe", None)

        # Result buckets
        r_upper = result.upper()
        if r_upper == "WIN":
            win += 1
        elif r_upper == "LOSS":
            loss += 1
        elif r_upper in ("BREAKEVEN", "BE"):
            be += 1
        elif r_upper == "CANCEL":
            cancel += 1
        elif r_upper == "OPEN":
            open_ += 1

        # PnL
        net_pnl += realized
        if ccy:
            pnl_ccy = pnl_ccy or ccy

        # MAE/MFE
        if mae is not None and mfe is not None:
            try:
                mae_sum += float(mae)
                mfe_sum += float(mfe)
                mae_n += 1
            except Exception:
                pass

        # Reasons
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1

        # HARD_FAIL check: look for exception for this run_id today
        exr = load_exception_for_run(date_path, str(run_id))
        if exr and str(exr.get("severity", "")).upper() == "HARD_FAIL":
            code = str(exr.get("code", "UNKNOWN"))
            hard_fails.append((str(run_id), code, str(exr.get("_path", ""))))

        per_run_lines.append(
            f"- {run_id} | {r_upper:<9} | pnl={realized:+.2f} {pnl_ccy or ''} | reason={reason}"
        )

    # Print report
    print(f"📊 Daily Report — {date_ymd} (UTC)")
    print("")
    print(f"Runs: {total}")
    print(f"WIN/LOSS/BE/CANCEL/OPEN: {win}/{loss}/{be}/{cancel}/{open_}")
    print(f"Net PnL: {net_pnl:+.2f} {pnl_ccy or ''}".rstrip())

    if mae_n > 0:
        print(f"Avg MAE: {mae_sum/mae_n:+.2f}")
        print(f"Avg MFE: {mfe_sum/mae_n:+.2f}")
    else:
        print("Avg MAE: n/a")
        print("Avg MFE: n/a")

    print("")
    if reasons:
        top = sorted(reasons.items(), key=lambda x: x[1], reverse=True)[:8]
        print("Top reasons:")
        for k, v in top:
            print(f"- {k}: {v}")
    else:
        print("Top reasons: n/a")

    print("")
    if hard_fails:
        print(f"Validator HARD_FAIL: {len(hard_fails)}")
        for rid, code, path in hard_fails[:10]:
            print(f"- {rid} | {code} | {path}")
    else:
        print("Validator HARD_FAIL: 0")

    print("")
    print("Per-run:")
    for line in per_run_lines[-15:]:
        print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
