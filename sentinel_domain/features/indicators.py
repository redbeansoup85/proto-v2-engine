from __future__ import annotations

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

