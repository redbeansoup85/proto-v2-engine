#!/usr/bin/env python3
"""
Card stats from Vault (v0.3.1)

✅ date range support: --from / --to  (inclusive, UTC)
✅ fail trend: HARD_FAIL code × card
✅ dedupe: run_id (keep last occurrence in runs_index.jsonl)
✅ quarantine handling (same as daily_report):
   - default: EXCLUDE quarantined runs (paths containing /quarantine/ or /_quarantine/)
   - opt-in:  --include-quarantine
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

VAULT_ROOT = Path("vault")
RUNS_INDEX = VAULT_ROOT / "manifests" / "runs_index.jsonl"


# ---------- time helpers ----------

def parse_ymd(s: str) -> datetime:
    # "2025-12-22" -> 2025-12-22 00:00:00+00:00
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def utc_today_ymd() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ---------- io helpers ----------

def safe_read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def parse_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def is_quarantined_path(p: str) -> bool:
    return ("/quarantine/" in p) or ("/_quarantine/" in p)


def extract_exec_date_parts(exec_path: str) -> Optional[Tuple[str, str, str]]:
    """
    Expected:
      .../vault/executions/YYYY/MM/DD/exec_<RUN_ID>.json
    Returns:
      ("YYYY","MM","DD") or None
    """
    try:
        after = exec_path.split("/executions/", 1)[1]
        parts = after.split("/")
        y, m, d = parts[0], parts[1], parts[2]
        if len(y) == 4 and len(m) == 2 and len(d) == 2:
            return y, m, d
        return None
    except Exception:
        return None


def exec_path_to_run_date(exec_path: str) -> Optional[datetime]:
    parts = extract_exec_date_parts(exec_path)
    if not parts:
        return None
    y, m, d = parts
    try:
        return parse_ymd(f"{y}-{m}-{d}")
    except Exception:
        return None


def exec_path_to_date_path(exec_path: str) -> Optional[str]:
    parts = extract_exec_date_parts(exec_path)
    if not parts:
        return None
    y, m, d = parts
    return f"{y}/{m}/{d}"


def load_exception_for_run(date_path: str, run_id: str) -> Optional[Dict[str, Any]]:
    ex_dir = VAULT_ROOT / "exceptions" / date_path
    if not ex_dir.exists():
        return None
    # match: exception_<RUN_ID>__*.json
    for p in sorted(ex_dir.glob(f"exception_{run_id}__*.json")):
        d = safe_read_json(p)
        if d:
            d["_path"] = str(p)
            return d
    return None


# ---------- logic helpers ----------

def is_valid_card_id(cid: Optional[str]) -> bool:
    if cid is None:
        return False
    c = str(cid).strip()
    if not c:
        return False
    cl = c.lower()
    return cl not in ("unknown", "...", "n/a", "none", "null")


def bucket() -> Dict[str, Any]:
    return {
        "runs": 0,
        "win": 0,
        "loss": 0,
        "open": 0,
        "cancel": 0,
        "be": 0,
        "net_pnl": 0.0,
        "pnl_n": 0,
        "mae_sum": 0.0,
        "mfe_sum": 0.0,
        "mae_n": 0,
        "reasons": {},  # reason -> count
        "hard_fail": 0,
    }


def inc_fail_trend(trend: Dict[str, Dict[str, int]], card_id: str, code: str) -> None:
    m = trend.setdefault(card_id, {})
    m[code] = m.get(code, 0) + 1


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser(description="Card stats from Vault")
    ap.add_argument("--date", help="UTC date YYYY-MM-DD (legacy single-day)")
    ap.add_argument("--from", dest="from_", help="UTC from YYYY-MM-DD (inclusive)")
    ap.add_argument("--to", help="UTC to YYYY-MM-DD (inclusive)")
    ap.add_argument("--mode", choices=["strategy", "judgment", "both"], default="both")
    ap.add_argument("--include-unknown", action="store_true", help="Include unknown/... card ids")
    ap.add_argument(
        "--include-quarantine",
        action="store_true",
        help="Include quarantined runs (paths containing /quarantine/ or /_quarantine/)",
    )
    args = ap.parse_args()

    # --- date window (inclusive) ---
    if args.from_ or args.to:
        d_from = parse_ymd(args.from_ or args.to)
        d_to = parse_ymd(args.to or args.from_)
    else:
        d = parse_ymd(args.date or utc_today_ymd())
        d_from = d_to = d

    # normalize if user swapped
    if d_from > d_to:
        d_from, d_to = d_to, d_from

    rows = parse_jsonl(RUNS_INDEX)

    # dedupe by run_id, keep last (later lines overwrite)
    by_run: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        run_id = r.get("run_id")
        exec_path = str(r.get("exec_path", "") or "")
        if not isinstance(run_id, str) or not run_id:
            continue
        if "/executions/" not in exec_path:
            continue

        # quarantine filter (default exclude)
        if (not args.include_quarantine) and is_quarantined_path(exec_path):
            continue

        run_date = exec_path_to_run_date(exec_path)
        if not run_date:
            continue

        if not (d_from <= run_date <= d_to):
            continue

        by_run[run_id] = r

    runs = list(by_run.values())

    by_strategy: Dict[str, Dict[str, Any]] = {}
    by_judgment: Dict[str, Dict[str, Any]] = {}

    # 🔥 fail trend: card -> code -> count
    fail_trend_strategy: Dict[str, Dict[str, int]] = {}
    fail_trend_judgment: Dict[str, Dict[str, int]] = {}

    for r in runs:
        run_id = str(r["run_id"])
        exec_path = str(r.get("exec_path", "") or "")

        exec_doc = safe_read_json(Path(exec_path)) or {}
        run_meta = (exec_doc.get("run", {}) or {})

        sid = str(run_meta.get("strategy_card_id", "unknown"))
        jid = str(run_meta.get("judgment_card_id", "unknown"))

        # drop fully-unknown runs unless include-unknown
        if not args.include_unknown:
            if (not is_valid_card_id(sid)) and (not is_valid_card_id(jid)):
                continue

        out_path = str(r.get("outcome_path", "") or "")
        outcome = safe_read_json(Path(out_path)) if out_path else None

        result = "UNKNOWN"
        reason = ""
        realized = 0.0
        mae = None
        mfe = None

        if outcome:
            labels = outcome.get("labels", {}) or {}
            result = str(labels.get("result", "UNKNOWN")).upper()
            reason = str(labels.get("reason", ""))

            pnl = outcome.get("pnl", {}) or {}
            realized = float(pnl.get("realized", 0.0) or 0.0)

            ex = outcome.get("excursions", {}) or {}
            mae = ex.get("mae")
            mfe = ex.get("mfe")

        date_path = exec_path_to_date_path(exec_path) or ""
        exr = load_exception_for_run(date_path, run_id) if date_path else None
        is_hard_fail = bool(exr and str(exr.get("severity", "")).upper() == "HARD_FAIL")
        fail_code = str(exr.get("code", "")) if exr else ""

        def apply(b: Dict[str, Any]) -> None:
            b["runs"] += 1
            if result == "WIN":
                b["win"] += 1
            elif result == "LOSS":
                b["loss"] += 1
            elif result == "OPEN":
                b["open"] += 1
            elif result == "CANCEL":
                b["cancel"] += 1
            elif result in ("BE", "BREAKEVEN"):
                b["be"] += 1

            b["net_pnl"] += realized
            b["pnl_n"] += 1

            if mae is not None and mfe is not None:
                try:
                    b["mae_sum"] += float(mae)
                    b["mfe_sum"] += float(mfe)
                    b["mae_n"] += 1
                except Exception:
                    pass

            if reason:
                rr = b["reasons"]
                rr[reason] = rr.get(reason, 0) + 1

            if is_hard_fail:
                b["hard_fail"] += 1

        if args.mode in ("strategy", "both") and (args.include_unknown or is_valid_card_id(sid)):
            b = by_strategy.setdefault(sid, bucket())
            apply(b)
            if is_hard_fail and fail_code:
                inc_fail_trend(fail_trend_strategy, sid, fail_code)

        if args.mode in ("judgment", "both") and (args.include_unknown or is_valid_card_id(jid)):
            b = by_judgment.setdefault(jid, bucket())
            apply(b)
            if is_hard_fail and fail_code:
                inc_fail_trend(fail_trend_judgment, jid, fail_code)

    # ---------- print ----------

    print(f"🧠 Card Stats — {d_from.date()} → {d_to.date()} (UTC)")
    print(f"runs (deduped): {len(runs)}\n")

    def print_table(title: str, data: Dict[str, Dict[str, Any]]) -> None:
        print(title)
        if not data:
            print("  n/a\n")
            return

        for cid, b in sorted(data.items(), key=lambda x: x[1]["runs"], reverse=True):
            runs_n = b["runs"]
            winrate = (b["win"] / runs_n * 100.0) if runs_n else 0.0
            failrate = (b["hard_fail"] / runs_n * 100.0) if runs_n else 0.0
            avg_pnl = (b["net_pnl"] / b["pnl_n"]) if b["pnl_n"] else 0.0
            avg_mae = (b["mae_sum"] / b["mae_n"]) if b["mae_n"] else None
            avg_mfe = (b["mfe_sum"] / b["mae_n"]) if b["mae_n"] else None

            top_reasons = sorted(b["reasons"].items(), key=lambda x: x[1], reverse=True)[:3]
            top_reasons_str = ", ".join([f"{k}:{v}" for k, v in top_reasons]) if top_reasons else "n/a"

            print(f"- {cid}")
            print(
                f"  runs={runs_n} | W/L/O={b['win']}/{b['loss']}/{b['open']} "
                f"| winrate={winrate:.1f}% | fail={b['hard_fail']} ({failrate:.1f}%)"
            )
            print(
                f"  avg_pnl={avg_pnl:+.2f} | net_pnl={b['net_pnl']:+.2f} "
                f"| avg_mae={avg_mae if avg_mae is not None else 'n/a'} "
                f"| avg_mfe={avg_mfe if avg_mfe is not None else 'n/a'}"
            )
            print(f"  top_reasons: {top_reasons_str}\n")

    if args.mode in ("strategy", "both"):
        print_table("Strategy cards:", by_strategy)

    if args.mode in ("judgment", "both"):
        print_table("Judgment cards:", by_judgment)

    # ---- FAIL TREND ----
    print("🔥 Fail trends (HARD_FAIL):")

    def print_fail_trend(title: str, trend: Dict[str, Dict[str, int]]) -> None:
        if not trend:
            print(f"\n{title}: n/a")
            return
        print(f"\n{title}:")
        for cid, codes in sorted(trend.items(), key=lambda kv: sum(kv[1].values()), reverse=True):
            total_fail = sum(codes.values())
            print(f"- {cid} (fails={total_fail})")
            for code, n in sorted(codes.items(), key=lambda x: x[1], reverse=True):
                print(f"  {code}: {n}")

    if args.mode in ("strategy", "both"):
        print_fail_trend("Strategy", fail_trend_strategy)
    if args.mode in ("judgment", "both"):
        print_fail_trend("Judgment", fail_trend_judgment)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
