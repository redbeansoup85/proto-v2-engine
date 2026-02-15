from __future__ import annotations

import math
from typing import Dict, List, Optional


def ema(values: List[float], period: int) -> Optional[float]:
    if period <= 0 or len(values) < period:
        return None
    k = 2.0 / (period + 1.0)
    current = sum(values[:period]) / float(period)
    for v in values[period:]:
        current = (v * k) + (current * (1.0 - k))
    return float(current)


def rsi(values: List[float], period: int = 14) -> Optional[float]:
    if period <= 0 or len(values) < (period + 1):
        return None

    gains: List[float] = []
    losses: List[float] = []
    for i in range(1, period + 1):
        delta = values[i] - values[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains) / float(period)
    avg_loss = sum(losses) / float(period)

    for i in range(period + 1, len(values)):
        delta = values[i] - values[i - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = ((avg_gain * (period - 1)) + gain) / float(period)
        avg_loss = ((avg_loss * (period - 1)) + loss) / float(period)

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def compute_vwap_from_candles(candles: List[Dict[str, object]], lookback: int) -> Optional[float]:
    # VWAP is candle-based approximation using typical price; not trade-level VWAP.
    # Uses typical=(h+l+c)/3 weighted by volume over trailing lookback candles.
    if lookback <= 0:
        return None

    tail = candles[-lookback:]
    if len(tail) < lookback:
        return None

    valid_count = 0
    numerator = 0.0
    denominator = 0.0
    for row in tail:
        if not isinstance(row, dict):
            continue
        try:
            h = float(row.get("h"))  # type: ignore[arg-type]
            l = float(row.get("l"))  # type: ignore[arg-type]
            c = float(row.get("c"))  # type: ignore[arg-type]
            v = float(row.get("v"))  # type: ignore[arg-type]
        except Exception:
            continue
        if not (math.isfinite(h) and math.isfinite(l) and math.isfinite(c) and math.isfinite(v)):
            continue
        typical = (h + l + c) / 3.0
        numerator += typical * v
        denominator += v
        valid_count += 1

    if valid_count < lookback or denominator <= 0.0:
        return None
    vwap = numerator / denominator
    if not math.isfinite(vwap):
        return None
    return float(vwap)


def compute_cvd_proxy_from_candles(candles: List[Dict[str, object]], lookback: int) -> Optional[float]:
    # CVD proxy is candle-based signed-volume sum; not trade-level CVD.
    # Uses +v when close>=open, otherwise -v over trailing lookback candles.
    if lookback <= 0:
        return None

    tail = candles[-lookback:]
    if len(tail) < lookback:
        return None

    valid_count = 0
    signed_sum = 0.0
    for row in tail:
        if not isinstance(row, dict):
            continue
        try:
            o = float(row.get("o"))  # type: ignore[arg-type]
            c = float(row.get("c"))  # type: ignore[arg-type]
            v = float(row.get("v"))  # type: ignore[arg-type]
        except Exception:
            continue
        if not (math.isfinite(o) and math.isfinite(c) and math.isfinite(v)):
            continue
        signed_sum += v if c >= o else -v
        valid_count += 1

    if valid_count < lookback:
        return None
    if not math.isfinite(signed_sum):
        return None
    return float(signed_sum)


def compute_tf_indicators(candles_by_tf: Dict[str, List[Dict[str, float]]]) -> Dict[str, Dict[str, Optional[float]]]:
    out: Dict[str, Dict[str, Optional[float]]] = {}
    for tf, rows in candles_by_tf.items():
        closes = [float(row["c"]) for row in rows if isinstance(row, dict) and "c" in row]
        out[tf] = {
            "ema20": ema(closes, 20),
            "ema50": ema(closes, 50),
            "ema200": ema(closes, 200),
            "rsi14": rsi(closes, 14),
        }
    return out
