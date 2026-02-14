#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_TF = "15m,1h,4h"
DEFAULT_LIMIT = 260


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


ROOT = _repo_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sdk.ta.indicators import ema, obv, rsi, slope, vwap
from tools.bybit_fetch_ohlcv import fetch_ohlcv


def _last_value(series: list[float | None], name: str) -> float:
    for value in reversed(series):
        if value is not None:
            return float(value)
    raise ValueError(f"{name} has no computable value")


def _tf_score(price: float, ema20_v: float, ema50_v: float, ema200_v: float, rsi14_v: float, vwap_v: float, obv_slope_v: float) -> int:
    score = 0

    if price > ema200_v:
        score += 15
    if ema20_v > ema50_v:
        score += 10
    if price > vwap_v:
        score += 10

    if 50 <= rsi14_v < 60:
        score += 8
    elif 60 <= rsi14_v < 70:
        score += 12
    elif rsi14_v >= 70:
        score += 6

    if obv_slope_v > 0:
        score += 10
    if price > ema20_v:
        score += 3

    if price < ema200_v:
        score -= 10
    if rsi14_v >= 75:
        score -= 5

    if score < 0:
        return 0
    if score > 100:
        return 100
    return int(score)


def _build_sha(repo_root: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--verify", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise ValueError(
            "cannot resolve git HEAD: "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    sha = proc.stdout.strip()
    if not re.fullmatch(r"[a-fA-F0-9]{7,64}", sha):
        raise ValueError(f"invalid build_sha: {sha}")
    return sha


def _compute_tf_block(rows: list[dict], tf: str) -> tuple[dict, int]:
    if len(rows) < 210:
        raise ValueError(f"{tf} requires at least 210 candles for EMA200, got {len(rows)}")

    closes = [float(r["close"]) for r in rows]
    volumes = [float(r["volume"]) for r in rows]

    ema20_series = ema(closes, 20)
    ema50_series = ema(closes, 50)
    ema200_series = ema(closes, 200)
    rsi14_series = rsi(closes, 14)
    vwap_series = vwap(rows)
    obv_series = obv(closes, volumes)
    obv_slope = slope(obv_series, window=20)

    price = closes[-1]
    ema20_v = _last_value(ema20_series, f"{tf}.ema20")
    ema50_v = _last_value(ema50_series, f"{tf}.ema50")
    ema200_v = _last_value(ema200_series, f"{tf}.ema200")
    rsi14_v = _last_value(rsi14_series, f"{tf}.rsi14")
    vwap_v = _last_value(vwap_series, f"{tf}.vwap")

    s_tf = _tf_score(
        price=price,
        ema20_v=ema20_v,
        ema50_v=ema50_v,
        ema200_v=ema200_v,
        rsi14_v=rsi14_v,
        vwap_v=vwap_v,
        obv_slope_v=obv_slope,
    )
    block = {
        "price": price,
        "ema20": ema20_v,
        "ema50": ema50_v,
        "ema200": ema200_v,
        "rsi14": rsi14_v,
        "vwap": vwap_v,
        "obv_slope": obv_slope,
    }
    return block, s_tf


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True, help="e.g. BTCUSDT")
    ap.add_argument("--out", required=True, help="output path")
    ap.add_argument("--tf", default=DEFAULT_TF, help='comma-separated timeframes, default "15m,1h,4h"')
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="candles per timeframe")
    ap.add_argument("--ci", action="store_true", help="force deterministic ts_iso")
    ap.add_argument("--bybit-base-url", default=None, help="override bybit base URL")
    args = ap.parse_args()

    tfs = [item.strip() for item in args.tf.split(",") if item.strip()]
    if not tfs:
        raise SystemExit("FAIL-CLOSED: --tf cannot be empty")
    if args.limit <= 0:
        raise SystemExit("FAIL-CLOSED: --limit must be > 0")

    bybit_base_url = args.bybit_base_url or os.getenv("BYBIT_BASE_URL") or "https://api.bybit.com"

    try:
        tf_blocks: dict[str, dict] = {}
        tf_scores: dict[str, int] = {}
        for tf in tfs:
            rows = fetch_ohlcv(symbol=args.symbol, tf=tf, limit=args.limit, bybit_base_url=bybit_base_url)
            block, s_tf = _compute_tf_block(rows, tf)
            tf_blocks[tf] = block
            tf_scores[tf] = s_tf

        for required in ("15m", "1h", "4h"):
            if required not in tf_blocks:
                raise ValueError(f"required timeframe missing for consensus: {required}")

        s15 = tf_scores["15m"]
        s1h = tf_scores["1h"]
        s4h = tf_scores["4h"]
        score_final = int(round((0.5 * s15) + (0.3 * s1h) + (0.2 * s4h)))

        price_4h = float(tf_blocks["4h"]["price"])
        ema200_4h = float(tf_blocks["4h"]["ema200"])
        if s15 >= 65 and s1h >= 55 and price_4h > ema200_4h:
            direction = "long"
        elif s15 <= 35 and s1h <= 45 and price_4h < ema200_4h:
            direction = "short"
        else:
            direction = "neutral"

        if price_4h < ema200_4h or score_final < 55:
            risk_level = "high"
        elif score_final >= 75 and price_4h > ema200_4h:
            risk_level = "low"
        else:
            risk_level = "medium"

        confidence = min(1.0, max(0.0, score_final / 100.0))
        flags: list[str] = []
        if price_4h > ema200_4h:
            flags.append("TF4H_ABOVE_EMA200")
        else:
            flags.append("TF4H_BELOW_EMA200")
        if direction == "neutral":
            flags.append("DIRECTION_UNCLEAR")

        ts_iso = "1970-01-01T00:00:00Z" if args.ci else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        repo_root = _repo_root()
        build_sha = _build_sha(repo_root)

        out = {
            "schema": "sentinel_snapshot.v0",
            "symbol": args.symbol,
            "ts_iso": ts_iso,
            "timeframes": tf_blocks,
            "derivatives": {"funding": None, "oi_delta": None},
            "score": {
                "s15": s15,
                "s1h": s1h,
                "s4h": s4h,
                "final": score_final,
                "direction": direction,
                "risk_level": risk_level,
                "confidence": confidence,
            },
            "flags": flags,
            "meta": {
                "producer": "sentinel.scoring.v0_2",
                "version": "0.2",
                "build_sha": build_sha,
            },
        }

        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"OK: wrote {out_path}")
        return 0
    except ValueError as exc:
        print(f"FAIL-CLOSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
