#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

import requests

BASE = "https://api.bybit.com/v5/market/kline"

TF_TO_INTERVAL = {
    "1m": "1",
    "3m": "3",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "2h": "120",
    "4h": "240",
    "1d": "D",
}

def fetch_ohlc(symbol: str, tf: str) -> dict:
    if tf not in TF_TO_INTERVAL:
        raise ValueError(f"unsupported tf={tf} (supported={sorted(TF_TO_INTERVAL.keys())})")

    params = {
        "category": "linear",
        "symbol": symbol,
        "interval": TF_TO_INTERVAL[tf],
        "limit": 1,
    }
    r = requests.get(BASE, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    # Bybit returns retCode/retMsg; fail-closed on nonzero or empty list
    if data.get("retCode") not in (0, "0", None):
        raise ValueError(f"bybit retCode={data.get('retCode')} retMsg={data.get('retMsg')}")

    result = data.get("result") or {}
    lst = result.get("list") or []
    if not lst:
        raise ValueError(f"bybit kline empty (symbol={symbol} tf={tf} interval={params['interval']})")

    k = lst[0]
    # list format: [startTime, open, high, low, close, volume, turnover]
    return {
        "open": float(k[1]),
        "high": float(k[2]),
        "low": float(k[3]),
        "close": float(k[4]),
        "volume": float(k[5]),
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--tf", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    try:
        ohlc = fetch_ohlc(args.symbol, args.tf)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        snapshot = {
            "symbol": args.symbol,
            "timeframe": args.tf,
            "ts": ts,
            "ohlc": ohlc,
        }

        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"OK: wrote {p}")
        return 0
    except Exception as e:
        print(f"FAIL-CLOSED: {e}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
