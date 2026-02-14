#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sdk.ta.indicators import ema, obv, rsi, slope, vwap


def _assert_len(name: str, values: list[float | None], expected: int) -> None:
    if len(values) != expected:
        raise AssertionError(f"{name} length mismatch: {len(values)} != {expected}")


def main() -> int:
    close = [100.0, 101.0, 100.5, 102.0, 103.0, 102.5, 104.0]
    volume = [10.0, 12.0, 11.0, 14.0, 15.0, 13.0, 16.0]
    ohlcv = [
        {"high": 101.0, "low": 99.0, "close": 100.0, "volume": 10.0},
        {"high": 102.0, "low": 100.0, "close": 101.0, "volume": 12.0},
        {"high": 101.0, "low": 100.0, "close": 100.5, "volume": 11.0},
        {"high": 103.0, "low": 101.0, "close": 102.0, "volume": 14.0},
        {"high": 104.0, "low": 102.0, "close": 103.0, "volume": 15.0},
        {"high": 103.0, "low": 101.0, "close": 102.5, "volume": 13.0},
        {"high": 105.0, "low": 103.0, "close": 104.0, "volume": 16.0},
    ]

    ema_vals = ema(close, period=3)
    rsi_vals = rsi(close, period=3)
    vwap_vals = vwap(ohlcv)
    obv_vals = obv(close, volume)
    slope_val = slope(ema_vals, window=3)

    n = len(close)
    _assert_len("ema", ema_vals, n)
    _assert_len("rsi", rsi_vals, n)
    _assert_len("vwap", vwap_vals, n)
    _assert_len("obv", obv_vals, n)
    if not isinstance(slope_val, float):
        raise AssertionError("slope must return float")

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
