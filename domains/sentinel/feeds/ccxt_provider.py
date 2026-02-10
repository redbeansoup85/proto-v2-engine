from __future__ import annotations

from datetime import datetime, timezone

import requests

from domains.sentinel.feeds.base import MarketDataProvider, MarketDataSnapshot, utc_now_iso


class CCXTProvider(MarketDataProvider):
    """
    Free REST polling provider for crypto quotes.
    Uses Binance public ticker endpoint as a no-auth source.
    """

    provider_id = "ccxt_provider"

    def __init__(self, *, timeout_s: int = 5, stale_after_s: int = 120) -> None:
        self.timeout_s = timeout_s
        self.stale_after_s = stale_after_s

    def fetch(self, asset: str) -> MarketDataSnapshot:
        pair = asset.upper()
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={pair}"
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
                raw_price = body.get("price")
                if raw_price is None:
                    quality_flags.append("PRICE_MISSING")
                else:
                    price = float(raw_price)
        except Exception:
            quality_flags.append("FETCH_ERROR")

        # Endpoint does not expose source ts in this route; best-effort use retrieved_at.
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
            asset=pair,
            price=price,
        )
