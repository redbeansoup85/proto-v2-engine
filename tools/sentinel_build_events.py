#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


TS_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z$")


def _load_json(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(obj, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return obj


def _prev_path(state_dir: Path, symbol_tf: str) -> Path:
    return state_dir / f"prev_{symbol_tf}.json"


def _item_key(item: dict) -> str:
    symbol = item.get("symbol")
    if not isinstance(symbol, str) or not symbol:
        raise ValueError("item.symbol must be non-empty string")
    timeframe = item.get("timeframe")
    if timeframe is None:
        return symbol
    if not isinstance(timeframe, str) or not timeframe:
        raise ValueError(f"{symbol}: item.timeframe must be non-empty string when present")
    if symbol.endswith(f"_{timeframe}"):
        return symbol
    return f"{symbol}_{timeframe}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-file", required=True)
    ap.add_argument("--state-dir", default="/tmp/metaos_domain_events/_state")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    try:
        summary = _load_json(Path(args.summary_file))
        ts = summary.get("ts")
        if not isinstance(ts, str) or not TS_RE.fullmatch(ts):
            raise ValueError("summary.ts must match yyyymmddTHHMMSSZ")
        items = summary.get("items")
        if not isinstance(items, list):
            raise ValueError("summary.items must be a list")

        state_dir = Path(args.state_dir)
        state_dir.mkdir(parents=True, exist_ok=True)

        events: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("summary.items entries must be objects")
            symbol_tf = _item_key(item)
            score = item.get("score")
            risk_level = item.get("risk_level")
            confidence = item.get("confidence")

            if not isinstance(score, int):
                raise ValueError(f"{symbol_tf}: item.score must be int")
            if risk_level not in ("low", "medium", "high"):
                raise ValueError(f"{symbol_tf}: item.risk_level invalid")
            if not isinstance(confidence, (int, float)):
                raise ValueError(f"{symbol_tf}: item.confidence must be number")

            prev_score: int | None = None
            prev_risk: str | None = None
            prev_conf: float | None = None
            prev_file = _prev_path(state_dir, symbol_tf)
            if prev_file.exists():
                prev = _load_json(prev_file)
                prev_score = prev.get("score")
                prev_risk = prev.get("risk_level")
                prev_conf = prev.get("confidence")
                if not isinstance(prev_score, int):
                    raise ValueError(f"{symbol_tf}: prev.score must be int")
                if prev_risk not in ("low", "medium", "high"):
                    raise ValueError(f"{symbol_tf}: prev.risk_level invalid")
                if not isinstance(prev_conf, (int, float)):
                    raise ValueError(f"{symbol_tf}: prev.confidence must be number")

            if prev_score is not None and abs(score - prev_score) >= 20:
                events.append(
                    {
                        "type": "SCORE_JUMP",
                        "symbol": symbol_tf,
                        "ts": ts,
                        "score": score,
                        "prev_score": prev_score,
                        "risk_level": risk_level,
                        "confidence": float(confidence),
                    }
                )
            if prev_risk is not None and prev_risk.upper() != "HIGH" and risk_level.upper() == "HIGH":
                events.append(
                    {
                        "type": "RISK_UP",
                        "symbol": symbol_tf,
                        "ts": ts,
                        "score": score,
                        "prev_risk": prev_risk,
                        "risk_level": risk_level,
                        "confidence": float(confidence),
                    }
                )
            if prev_conf is not None and (float(prev_conf) - float(confidence)) >= 0.2:
                events.append(
                    {
                        "type": "CONF_DROP",
                        "symbol": symbol_tf,
                        "ts": ts,
                        "score": score,
                        "prev_confidence": float(prev_conf),
                        "confidence": float(confidence),
                        "risk_level": risk_level,
                    }
                )

            prev_file.write_text(
                json.dumps(
                    {
                        "symbol": symbol_tf,
                        "score": score,
                        "risk_level": risk_level,
                        "confidence": float(confidence),
                        "ts": ts,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

        out = {
            "schema": "sentinel_events.v0",
            "ts": ts,
            "events": events,
            "count": len(events),
        }
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"OK: wrote {out_path}")
        return 0
    except Exception as exc:
        print(f"FAIL-CLOSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
