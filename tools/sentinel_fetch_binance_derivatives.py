#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import requests
from pathlib import Path
from datetime import datetime, timezone

OI_URL = "https://fapi.binance.com/fapi/v1/openInterest"
LS_URL = "https://fapi.binance.com/futures/data/globalLongShortAccountRatio"

def fetch(symbol: str):
    oi = requests.get(OI_URL, params={"symbol": symbol}, timeout=10).json()
    ls = requests.get(LS_URL, params={"symbol": symbol, "period": "5m", "limit": 1}, timeout=10).json()[0]
    return {
        "open_interest": float(oi["openInterest"]),
        "long_short_ratio": float(ls["longShortRatio"]),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    data = fetch(args.symbol)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    out = {
        "symbol": args.symbol,
        "ts": ts,
        "derivatives": data,
    }

    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"OK: wrote {p}")

if __name__ == "__main__":
    main()
