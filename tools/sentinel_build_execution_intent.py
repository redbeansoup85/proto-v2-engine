#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _now_ts_iso() -> str:
    # UTC ISO-8601 seconds precision
    proc = subprocess.run(
        ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise ValueError("cannot compute ts_iso")
    return proc.stdout.strip()


def _build_sha(repo_root: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--verify", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        return "n/a"
    sha = proc.stdout.strip()
    return sha if re.fullmatch(r"[a-fA-F0-9]{7,64}", sha) else "n/a"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _get_final(item: dict) -> dict:
    """
    Prefer consensus output in item['final'].
    Fallback to item top-level fields (score/direction/risk_level/confidence) if needed.
    """
    f = item.get("final")
    if isinstance(f, dict):
        return f
    return {}


def _as_float(v: Any, name: str) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    raise ValueError(f"{name} must be numeric")


def _as_int(v: Any, name: str) -> int:
    if isinstance(v, int):
        return int(v)
    if isinstance(v, float) and float(v).is_integer():
        return int(v)
    raise ValueError(f"{name} must be int-like")


def _select_signal(item: dict) -> tuple[int, str | None, str, float, str | None]:
    """
    Returns: (score, direction, risk_level, confidence, snapshot_path)
    - direction can be None
    """
    final = _get_final(item)

    # consensus-first
    if final:
        score = _as_int(final.get("final_score"), "final.final_score")
        direction = final.get("final_direction")
        risk = final.get("final_risk_level")
        conf = _as_float(final.get("final_confidence"), "final.final_confidence")
        snap = final.get("final_snapshot_path")
        if direction not in (None, "long", "short", "neutral"):
            raise ValueError("final.final_direction invalid")
        if risk not in ("low", "medium", "high"):
            raise ValueError("final.final_risk_level invalid")
        if not isinstance(snap, str) or not snap:
            snap = None
        return score, direction, risk, conf, snap

    # raw fallback
    score = _as_int(item.get("score"), "item.score")
    direction = item.get("direction")
    risk = item.get("risk_level")
    conf = _as_float(item.get("confidence"), "item.confidence")
    snap = item.get("snapshot_path")
    if direction not in (None, "long", "short", "neutral"):
        raise ValueError("item.direction invalid")
    if risk not in ("low", "medium", "high"):
        raise ValueError("item.risk_level invalid")
    if not isinstance(snap, str) or not snap:
        snap = None
    return score, direction, risk, conf, snap


def _evaluate_trigger(
    *,
    score: int,
    direction: str | None,
    risk_level: str,
    confidence: float,
    oi_delta_pct: float | None,
) -> tuple[bool, str]:
    """
    Returns (triggered, reason_code).
    - reason_code is stable text for audit/filters.
    """
    # Safety veto
    if oi_delta_pct is not None and oi_delta_pct <= -0.20:
        return (False, "NO_TRADE_OI_DROP_VETO")

    if score >= 75 and direction in ("long", "short") and risk_level in ("low", "medium") and confidence >= 0.70:
        return (True, "EXECUTE_CONDITIONS_MET")

    return (False, "NO_ACTION_CONDITIONS_NOT_MET")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-file", required=True)
    ap.add_argument("--outbox", required=True, help="directory to write intent JSON")
    ap.add_argument("--dry-run", type=int, default=1, help="1 = DRY_RUN (default), 0 = live intent")
    args = ap.parse_args()

    try:
        summary_path = Path(args.summary_file)
        outbox_dir = Path(args.outbox)
        outbox_dir.mkdir(parents=True, exist_ok=True)

        summary = _load_json(summary_path)
        items = summary.get("items")
        if not isinstance(items, list):
            raise ValueError("summary.items must be a list")

        ts = summary.get("ts")
        if not isinstance(ts, str) or not ts:
            raise ValueError("summary.ts must be non-empty string")

        repo_root = _repo_root()
        build_sha = _build_sha(repo_root)

        intents: list[dict] = []

        for item in items:
            if not isinstance(item, dict):
                raise ValueError("summary.items entries must be objects")

            symbol = item.get("symbol")
            if not isinstance(symbol, str) or not symbol:
                raise ValueError("item.symbol must be non-empty string")

            # optional - included by build_summary consensus path in your pipeline
            oi_delta_pct = item.get("oi_delta_pct")
            if oi_delta_pct is not None and not isinstance(oi_delta_pct, (int, float)):
                raise ValueError(f"{symbol}: item.oi_delta_pct must be numeric when present")
            oi_delta_pct_v = float(oi_delta_pct) if oi_delta_pct is not None else None

            score, direction, risk, conf, snap = _select_signal(item)
            triggered, reason = _evaluate_trigger(
                score=score,
                direction=direction,
                risk_level=risk,
                confidence=conf,
                oi_delta_pct=oi_delta_pct_v,
            )

            intents.append(
                {
                    "symbol": symbol,
                    "timeframe": item.get("timeframe"),  # optional
                    "final_score": score,
                    "final_direction": direction,
                    "final_risk_level": risk,
                    "final_confidence": conf,
                    "oi_delta_pct": oi_delta_pct_v,
                    "snapshot_path": snap,
                    "triggered": triggered,
                    "reason_code": reason,
                }
            )

        # execution_intent.v1 envelope (fail-closed schema discipline)
        event = {
            "schema": "execution_intent.v1",
            "domain": "SENTINEL_EXEC",
            "kind": "INTENT",
            "event_id": f"intent_{ts}",
            "ts_iso": _now_ts_iso(),
            "intent": {
                "ts": ts,
                "dry_run": bool(int(args.dry_run)),
                "items": intents,
            },
            "meta": {
                "producer": "sentinel.exec",
                "version": "0",
                "build_sha": build_sha,
            },
            "evidence_refs": [
                {
                    "ref_kind": "FILEPATH",
                    "ref": str(summary_path),
                }
            ],
        }

        out_path = outbox_dir / f"intent_{ts}.json"
        out_path.write_text(json.dumps(event, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"OK: wrote {out_path}")
        return 0

    except Exception as exc:
        print(f"FAIL-CLOSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
