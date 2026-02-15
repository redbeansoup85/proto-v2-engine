from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

BYBIT_BASE_URL = "https://api.bybit.com"
INTERVAL_MAP = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "4h": "240"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _iso_from_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _http_get_json(url: str, timeout_sec: float = 10.0) -> Dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout_sec) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def _build_kline_url(asset: str, tf: str, market_type: str, limit: int) -> str:
    interval = INTERVAL_MAP.get(tf)
    if not interval:
        raise ValueError("unsupported_tf:%s" % tf)
    category = "linear" if market_type == "perp" else "spot"
    query = urllib.parse.urlencode(
        {
            "category": category,
            "symbol": asset,
            "interval": interval,
            "limit": str(limit),
        }
    )
    return "%s/v5/market/kline?%s" % (BYBIT_BASE_URL, query)


def _parse_kline_rows(rows: List[Any]) -> List[Dict[str, Any]]:
    parsed: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 6:
            continue
        try:
            ts_ms = int(row[0])
            parsed.append(
                {
                    "t": _iso_from_ms(ts_ms),
                    "o": float(row[1]),
                    "h": float(row[2]),
                    "l": float(row[3]),
                    "c": float(row[4]),
                    "v": float(row[5]),
                    "_ts_ms": ts_ms,
                }
            )
        except Exception:
            continue
    parsed.sort(key=lambda x: int(x["_ts_ms"]))
    for item in parsed:
        item.pop("_ts_ms", None)
    return parsed


def fetch_raw_market_bundle(
    asset: str,
    tfs: List[str],
    venue: str = "bybit",
    market_type: str = "perp",
    limit: int = 300,
    http_get_json: Optional[Callable[[str, float], Dict[str, Any]]] = None,
    timeout_sec: float = 10.0,
) -> Dict[str, Any]:
    get_json = http_get_json or _http_get_json
    start = time.time()
    candles: Dict[str, List[Dict[str, Any]]] = {}
    endpoints: List[str] = []
    errors: List[Dict[str, str]] = []

    for tf in tfs:
        if tf not in INTERVAL_MAP:
            candles[tf] = []
            errors.append({"tf": tf, "type": "unsupported_tf", "message": "unsupported timeframe"})
            continue

        url = _build_kline_url(asset=asset, tf=tf, market_type=market_type, limit=limit)
        endpoints.append(url)
        try:
            payload = get_json(url, timeout_sec)
            rows = (((payload or {}).get("result") or {}).get("list") or [])
            parsed = _parse_kline_rows(rows if isinstance(rows, list) else [])
            candles[tf] = parsed
            if not parsed:
                errors.append({"tf": tf, "type": "empty_rows", "message": "no candle rows"})
        except Exception as exc:
            candles[tf] = []
            errors.append({"tf": tf, "type": "http_error", "message": str(exc)})

    latency_ms = int((time.time() - start) * 1000)
    return {
        "schema": "raw_market_bundle.v1",
        "venue": venue,
        "market_type": market_type,
        "asset": asset,
        "ts_utc": _utc_now_iso(),
        "candles": candles,
        "deriv": {},
        "proof": {
            "source": "rest",
            "endpoints": endpoints,
            "latency_ms": latency_ms,
            "errors": errors,
        },
    }

