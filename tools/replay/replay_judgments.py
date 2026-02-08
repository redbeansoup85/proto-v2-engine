#!/usr/bin/env python3
"""
Replay + Outcome Join Report (stdlib-only, fail-closed)

Inputs:
- audits/sentinel/judgment_events_chain.jsonl
- audits/sentinel/outcomes/<judgment_id>.json (optional)

Outputs:
- JSON report to stdout:
  - totals
  - per_card stats
  - per_rule stats
"""
from __future__ import annotations

import json
import math
import re
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_CHAIN = Path("audits/sentinel/judgment_events_chain.jsonl")
DEFAULT_OUT_DIR = Path("audits/sentinel/outcomes")

RE_NUM = re.compile(r"^-?\d+(\.\d+)?$")


def _fail(code: str, detail: str = "") -> None:
    raise SystemExit(json.dumps({"error": code, "detail": detail}, sort_keys=True))


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        _fail("CHAIN_MISSING", str(path))
    rows: List[Dict[str, Any]] = []
    for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except Exception:
            _fail("CHAIN_BAD_JSON", f"line={i}")
        if not isinstance(obj, dict):
            _fail("CHAIN_NOT_OBJECT", f"line={i}")
        rows.append(obj)
    if not rows:
        _fail("CHAIN_EMPTY", str(path))
    return rows


def _read_outcome(outcome_dir: Path, judgment_id: str) -> Optional[Dict[str, Any]]:
    p = outcome_dir / f"{judgment_id}.json"
    if not p.exists():
        return None
    try:
        obj = json.loads(p.read_text(encoding="utf-8").strip())
    except Exception:
        _fail("OUTCOME_BAD_JSON", str(p))
    if not isinstance(obj, dict) or obj.get("schema") != "outcome_record.v1":
        _fail("OUTCOME_SCHEMA_MISMATCH", str(p))
    return obj


def _parse_num(v: Any) -> Optional[float]:
    if isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v)):
        return float(v)
    if isinstance(v, str) and RE_NUM.match(v.strip()):
        try:
            return float(v)
        except Exception:
            return None
    return None


def _ensure_bucket(m: Dict[str, Any], key: str) -> Dict[str, Any]:
    if key not in m:
        m[key] = {
            "count": 0,
            "labels": {"WIN": 0, "LOSS": 0, "BE": 0, "UNKNOWN": 0},
            "pnl_r": {"n": 0, "sum": 0.0},
        }
    return m[key]


def main() -> int:
    ap = argparse.ArgumentParser(description="Replay + outcome join report")
    ap.add_argument("--chain-path", default=str(DEFAULT_CHAIN))
    ap.add_argument("--outcome-dir", default=str(DEFAULT_OUT_DIR))
    args = ap.parse_args()
    chain_path = Path(args.chain_path)
    outcome_dir = Path(args.outcome_dir)
    events = _read_jsonl(chain_path)

    totals = {
        "events": 0,
        "with_outcome": 0,
        "labels": {"WIN": 0, "LOSS": 0, "BE": 0, "UNKNOWN": 0},
        "pnl_r": {"n": 0, "sum": 0.0},
    }

    per_card: Dict[str, Any] = {}
    per_rule: Dict[str, Any] = {}

    for evt in events:
        if evt.get("schema") != "judgment_event.v1":
            continue

        totals["events"] += 1

        jid = str(evt.get("judgment_id", ""))
        card_id = str(evt.get("card_id", "n/a"))
        rule_hits = evt.get("rule_hits") or []
        if not isinstance(rule_hits, list):
            rule_hits = []

        oc = _read_outcome(outcome_dir, jid)
        label = "UNKNOWN"
        pnl_r_num: Optional[float] = None

        if oc is not None:
            totals["with_outcome"] += 1
            label = str(oc.get("label", "UNKNOWN"))
            if label not in totals["labels"]:
                label = "UNKNOWN"
            pnl_r_num = _parse_num(oc.get("pnl_r", "n/a"))

        totals["labels"][label] += 1
        if pnl_r_num is not None:
            totals["pnl_r"]["n"] += 1
            totals["pnl_r"]["sum"] += pnl_r_num

        cb = _ensure_bucket(per_card, card_id)
        cb["count"] += 1
        cb["labels"][label] += 1
        if pnl_r_num is not None:
            cb["pnl_r"]["n"] += 1
            cb["pnl_r"]["sum"] += pnl_r_num

        for rh in rule_hits:
            rb = _ensure_bucket(per_rule, str(rh))
            rb["count"] += 1
            rb["labels"][label] += 1
            if pnl_r_num is not None:
                rb["pnl_r"]["n"] += 1
                rb["pnl_r"]["sum"] += pnl_r_num

    def _finalize(b: Dict[str, Any]) -> Dict[str, Any]:
        n = b["pnl_r"]["n"]
        s = b["pnl_r"]["sum"]
        b["pnl_r"]["avg"] = (s / n) if n else "n/a"
        return b

    per_card = {k: _finalize(v) for k, v in per_card.items()}
    per_rule = {k: _finalize(v) for k, v in per_rule.items()}

    report = {
        "schema": "replay_report.v1",
        "chain_path": str(chain_path),
        "outcome_dir": str(outcome_dir),
        "totals": {
            **totals,
            "pnl_r": {
                "n": totals["pnl_r"]["n"],
                "sum": totals["pnl_r"]["sum"],
                "avg": (totals["pnl_r"]["sum"] / totals["pnl_r"]["n"]) if totals["pnl_r"]["n"] else "n/a",
            },
        },
        "per_card": per_card,
        "per_rule": per_rule,
    }

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
