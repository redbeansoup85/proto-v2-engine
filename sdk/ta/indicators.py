from __future__ import annotations

from typing import Any


def _require_numeric_series(series: list[float], name: str) -> None:
    if not isinstance(series, list):
        raise ValueError(f"{name} must be a list")
    for i, value in enumerate(series):
        if value is None or not isinstance(value, (int, float)):
            raise ValueError(f"{name}[{i}] must be numeric")


def ema(series: list[float], period: int) -> list[float | None]:
    _require_numeric_series(series, "series")
    if period <= 0:
        raise ValueError("period must be > 0")
    n = len(series)
    if n == 0:
        return []
    if period > n:
        return [None] * n

    out: list[float | None] = [None] * n
    seed = sum(float(v) for v in series[:period]) / period
    out[period - 1] = seed
    alpha = 2.0 / (period + 1.0)

    prev = seed
    for i in range(period, n):
        prev = alpha * float(series[i]) + (1.0 - alpha) * prev
        out[i] = prev
    return out


def rsi(series: list[float], period: int = 14) -> list[float | None]:
    _require_numeric_series(series, "series")
    if period <= 0:
        raise ValueError("period must be > 0")
    n = len(series)
    if n == 0:
        return []
    if n <= period:
        return [None] * n

    out: list[float | None] = [None] * n

    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        diff = float(series[i]) - float(series[i - 1])
        if diff > 0:
            gains += diff
        elif diff < 0:
            losses += -diff

    avg_gain = gains / period
    avg_loss = losses / period

    if avg_loss == 0.0 and avg_gain == 0.0:
        out[period] = 50.0
    elif avg_loss == 0.0:
        out[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        out[period] = 100.0 - (100.0 / (1.0 + rs))

    for i in range(period + 1, n):
        diff = float(series[i]) - float(series[i - 1])
        gain = diff if diff > 0 else 0.0
        loss = -diff if diff < 0 else 0.0
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period

        if avg_loss == 0.0 and avg_gain == 0.0:
            out[i] = 50.0
        elif avg_loss == 0.0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - (100.0 / (1.0 + rs))

    return out


def vwap(ohlcv: list[dict[str, Any]]) -> list[float | None]:
    if not isinstance(ohlcv, list):
        raise ValueError("ohlcv must be a list")

    out: list[float | None] = []
    cumulative_tpv = 0.0
    cumulative_vol = 0.0

    for i, row in enumerate(ohlcv):
        if not isinstance(row, dict):
            raise ValueError(f"ohlcv[{i}] must be an object")

        for key in ("high", "low", "close"):
            if key not in row or row[key] is None or not isinstance(row[key], (int, float)):
                raise ValueError(f"ohlcv[{i}].{key} must be numeric")

        vol = row.get("volume")
        if vol is None:
            out.append(None)
            continue
        if not isinstance(vol, (int, float)):
            raise ValueError(f"ohlcv[{i}].volume must be numeric when present")
        vol_f = float(vol)
        if vol_f < 0:
            raise ValueError(f"ohlcv[{i}].volume must be >= 0")
        if vol_f == 0.0:
            out.append(None)
            continue

        tp = (float(row["high"]) + float(row["low"]) + float(row["close"])) / 3.0
        cumulative_tpv += tp * vol_f
        cumulative_vol += vol_f
        out.append(cumulative_tpv / cumulative_vol)

    return out


def obv(close: list[float], volume: list[float]) -> list[float | None]:
    _require_numeric_series(close, "close")
    _require_numeric_series(volume, "volume")
    if len(close) != len(volume):
        raise ValueError("close and volume lengths must match")
    n = len(close)
    if n == 0:
        return []

    out: list[float | None] = [None] * n
    running = 0.0
    out[0] = running

    for i in range(1, n):
        if float(close[i]) > float(close[i - 1]):
            running += float(volume[i])
        elif float(close[i]) < float(close[i - 1]):
            running -= float(volume[i])
        out[i] = running
    return out


def slope(series: list[float], window: int) -> float:
    if not isinstance(series, list):
        raise ValueError("series must be a list")
    if window < 2:
        raise ValueError("window must be >= 2")

    non_none = [float(v) for v in series if v is not None]
    if len(non_none) < window:
        raise ValueError("insufficient non-None points")
    ys = non_none[-window:]

    n = float(window)
    x_mean = (n - 1.0) / 2.0
    y_mean = sum(ys) / n

    numerator = 0.0
    denominator = 0.0
    for i, y in enumerate(ys):
        dx = float(i) - x_mean
        numerator += dx * (y - y_mean)
        denominator += dx * dx

    if denominator == 0.0:
        raise ValueError("invalid window for slope")
    return numerator / denominator
