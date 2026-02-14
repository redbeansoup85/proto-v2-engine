#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.parse
import urllib.request


def tf_to_bybit_interval(tf: str) -> str:
    mapping = {
        "1m": "1",
        "3m": "3",
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "1h": "60",
        "2h": "120",
        "4h": "240",
        "6h": "360",
        "12h": "720",
        "1d": "D",
    }
    if tf not in mapping:
        raise ValueError(f"unsupported timeframe: {tf}")
    return mapping[tf]


def fetch_ohlcv(
    symbol: str,
    tf: str,
    limit: int,
    bybit_base_url: str = "https://api.bybit.com",
) -> list[dict]:
    if not symbol:
        raise ValueError("symbol is required")
    if limit <= 0:
        raise ValueError("limit must be > 0")
    interval = tf_to_bybit_interval(tf)

    query = urllib.parse.urlencode(
        {
            "category": "linear",
            "symbol": symbol,
            "interval": interval,
            "limit": str(limit),
        }
    )
    url = f"{bybit_base_url.rstrip('/')}/v5/market/kline?{query}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        raw = resp.read().decode("utf-8", errors="strict")
    payload = json.loads(raw)

    rows = ((payload.get("result") or {}).get("list")) or []
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"no kline rows for {symbol} {tf}")

    out: list[dict] = []
    for i, row in enumerate(rows):
        if not isinstance(row, list) or len(row) < 6:
            raise ValueError(f"invalid kline row at index {i}")
        out.append(
            {
                "ts_ms": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            }
        )

    out.sort(key=lambda x: x["ts_ms"])
    return out
