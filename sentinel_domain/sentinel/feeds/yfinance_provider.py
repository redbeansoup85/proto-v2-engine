from __future__ import annotations

from datetime import datetime, timezone

import requests

from sentinel_domain.sentinel.feeds.base import MarketDataProvider, MarketDataSnapshot, utc_now_iso


class YFinanceProvider(MarketDataProvider):
    """
    Best-effort equities provider using Yahoo chart endpoint.
    No external yfinance dependency required.
    """

    provider_id = "yfinance_provider"

    def __init__(self, *, timeout_s: int = 5, stale_after_s: int = 600) -> None:
        self.timeout_s = timeout_s
        self.stale_after_s = stale_after_s

    def fetch(self, asset: str) -> MarketDataSnapshot:
        symbol = asset.upper()
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=1m"
        retrieved_at = utc_now_iso()
        quality_flags: list[str] = []
        source_timestamp = retrieved_at
        price: float | None = None

        try:
            resp = requests.get(url, timeout=self.timeout_s)
            if resp.status_code != 200:
                quality_flags.append("HTTP_NON_200")
            else:
                body = resp.json()
                result = (((body.get("chart") or {}).get("result")) or [None])[0] or {}
                meta = result.get("meta") or {}
                regular_price = meta.get("regularMarketPrice")
                ts = meta.get("regularMarketTime")
                if regular_price is None:
                    quality_flags.append("PRICE_MISSING")
                else:
                    price = float(regular_price)
                if isinstance(ts, int):
                    source_timestamp = datetime.fromtimestamp(ts, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
                else:
                    quality_flags.append("SOURCE_TS_MISSING")
        except Exception:
            quality_flags.append("FETCH_ERROR")

        src_dt = datetime.fromisoformat(source_timestamp.replace("Z", "+00:00"))
        ret_dt = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
        stale = (ret_dt - src_dt).total_seconds() > self.stale_after_s or "FETCH_ERROR" in quality_flags
        if stale:
            quality_flags.append("STALE_DATA")

        return MarketDataSnapshot(
            provider_id=self.provider_id,
            retrieved_at=retrieved_at,
            source_timestamp=source_timestamp,
            staleness_flag=stale,
            quality_flags=quality_flags,
            asset=symbol,
            price=price,
        )
