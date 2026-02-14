#!/usr/bin/env python3
import argparse, json, time, urllib.request
from pathlib import Path

BYBIT = "https://api.bybit.com"

def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
    return json.loads(raw)

def ema(values, period: int):
    if not values:
        return []
    k = 2 / (period + 1)
    out = []
    e = values[0]
    out.append(e)
    for v in values[1:]:
        e = v * k + e * (1 - k)
        out.append(e)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--interval", default="15")  # minutes
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ts", type=int, default=None, help="override ts (for CI)")
    args = ap.parse_args()

    symbol = args.symbol
    interval = args.interval
    limit = args.limit

    # Bybit v5 public endpoints (no auth)
    ticker_url = f"{BYBIT}/v5/market/tickers?category=linear&symbol={symbol}"
    kline_url  = f"{BYBIT}/v5/market/kline?category=linear&symbol={symbol}&interval={interval}&limit={limit}"

    tkr = get_json(ticker_url)
    kln = get_json(kline_url)

    # defensive
    tick_list = (tkr.get("result") or {}).get("list") or []
    if not tick_list:
        raise SystemExit(f"FAIL: no ticker list for {symbol}")
    tick = tick_list[0]

    rows = (kln.get("result") or {}).get("list") or []
    if not rows:
        raise SystemExit(f"FAIL: no kline rows for {symbol}")

    # Bybit kline row: [startTime, open, high, low, close, volume, turnover]
    rows = list(reversed(rows))  # oldest -> newest
    closes = [float(r[4]) for r in rows]
    vols   = [float(r[5]) for r in rows]

    ema20 = ema(closes, 20)[-1]
    last_close = closes[-1]
    last_vol = vols[-1]
    vol_mean = sum(vols[-50:]) / max(1, len(vols[-50:]))
    vol_spike = (last_vol / vol_mean) if vol_mean > 0 else 0.0

    ts = args.ts if args.ts is not None else int(time.time())

    # "norm" = Gate input용 최소 스냅샷 (네 시스템에 맞게 확장 가능)
    norm = {
        "schema": "sentinel_snapshot.v1",
        "ts": ts,
        "exchange": "bybit",
        "market": "linear",
        "symbol": symbol,
        "tf": f"{interval}m",
        "price": {
            "last": float(tick.get("lastPrice") or last_close),
            "mark": float(tick.get("markPrice") or 0.0),
            "index": float(tick.get("indexPrice") or 0.0),
        },
        "kline": {
            "limit": limit,
            "close": last_close,
            "ema20": ema20,
            "vol_last": last_vol,
            "vol_mean_50": vol_mean,
            "vol_spike": vol_spike,
        },
        "meta": {
            "source_urls": {"ticker": ticker_url, "kline": kline_url},
        }
    }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(norm, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"OK: wrote {args.out}")

if __name__ == "__main__":
    main()
