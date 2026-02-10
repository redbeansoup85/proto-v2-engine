from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Callable

from sentinel.feeds.base import MarketDataProvider, MarketDataSnapshot, utc_now_iso

try:
    import ccxt  # type: ignore
except Exception:  # pragma: no cover - optional dependency path
    ccxt = None


TIMEFRAME_SECONDS: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
}

STALE_THRESHOLDS_SECONDS: dict[str, int] = {
    "1m": 120,
    "5m": 600,
    "15m": 1800,
    "1h": 7200,
    "4h": 28800,
}


class CCXTProvider(MarketDataProvider):
    """
    Robust CCXT REST polling provider (optional dependency).
    Never raises to callers; always returns quality-scored snapshot.
    """

    def __init__(
        self,
        *,
        exchange_id: str = "binance",
        timeout_s: int = 10,
        exchange_factory: Callable[[], Any] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self.exchange_id = exchange_id
        self.provider_id = f"ccxt:{exchange_id}"
        self.timeout_s = timeout_s
        self._exchange_factory = exchange_factory
        self._sleep_fn = sleep_fn or time.sleep
        self._exchange: Any | None = None
        self._markets_loaded = False

    def _make_error_snapshot(self, *, asset: str, quality_flags: list[str]) -> MarketDataSnapshot:
        retrieved_at = utc_now_iso()
        flags = list(dict.fromkeys(quality_flags + ["stale"]))
        return MarketDataSnapshot(
            provider_id=self.provider_id,
            retrieved_at=retrieved_at,
            source_timestamp=None,
            staleness_flag=True,
            quality_flags=flags,
            asset=asset,
            price=None,
            candles=[],
        )

    def _get_exchange(self) -> Any:
        if self._exchange is not None:
            return self._exchange
        if self._exchange_factory is not None:
            self._exchange = self._exchange_factory()
            return self._exchange
        if ccxt is None:
            raise RuntimeError("ccxt_not_installed")
        cls = getattr(ccxt, self.exchange_id, None)
        if cls is None:
            raise RuntimeError(f"unknown_exchange:{self.exchange_id}")
        self._exchange = cls({"enableRateLimit": True, "timeout": self.timeout_s * 1000})
        return self._exchange

    def _ensure_markets(self, exchange: Any) -> None:
        if self._markets_loaded:
            return
        exchange.load_markets()
        self._markets_loaded = True

    def get_ohlcv(self, *, asset: str, timeframe: str, limit: int = 50) -> MarketDataSnapshot:
        if timeframe not in TIMEFRAME_SECONDS:
            return self._make_error_snapshot(asset=asset, quality_flags=["exchange_error", "unsupported_timeframe"])

        quality_flags: list[str] = []
        retrieved_at = utc_now_iso()
        candles: list[list[float | int]] = []

        try:
            exchange = self._get_exchange()
            self._ensure_markets(exchange)
        except Exception:
            return self._make_error_snapshot(asset=asset, quality_flags=["exchange_error"])

        markets = getattr(exchange, "markets", {}) or {}
        if asset not in markets:
            return self._make_error_snapshot(asset=asset, quality_flags=["exchange_error", "unsupported_symbol"])

        ex_timeframes = getattr(exchange, "timeframes", {}) or {}
        if ex_timeframes and timeframe not in ex_timeframes:
            return self._make_error_snapshot(asset=asset, quality_flags=["exchange_error", "unsupported_timeframe"])

        attempts = (0.5, 1.0, 2.0)
        for idx, backoff in enumerate(attempts, start=1):
            try:
                candles = exchange.fetch_ohlcv(asset, timeframe=timeframe, limit=limit) or []
                break
            except Exception as exc:
                msg = str(exc).lower()
                if "rate limit" in msg or "too many requests" in msg or "429" in msg:
                    quality_flags.append("rate_limited")
                else:
                    quality_flags.append("exchange_error")
                if idx < len(attempts):
                    self._sleep_fn(backoff)
                else:
                    return self._make_error_snapshot(asset=asset, quality_flags=quality_flags)

        if not candles:
            return self._make_error_snapshot(asset=asset, quality_flags=quality_flags + ["missing_candle"])

        # Expect [timestamp_ms, open, high, low, close, volume]
        last = candles[-1]
        if not isinstance(last, list) or len(last) < 5 or not isinstance(last[0], (int, float)):
            return self._make_error_snapshot(asset=asset, quality_flags=quality_flags + ["exchange_error", "missing_candle"])

        source_ts_ms = int(last[0])
        source_timestamp = datetime.fromtimestamp(source_ts_ms / 1000, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        price = float(last[4]) if isinstance(last[4], (int, float)) else None
        if price is None:
            quality_flags.append("exchange_error")

        # gap/missing candle check
        expected_step_ms = TIMEFRAME_SECONDS[timeframe] * 1000
        for i in range(1, len(candles)):
            prev_ts = candles[i - 1][0] if isinstance(candles[i - 1], list) and candles[i - 1] else None
            curr_ts = candles[i][0] if isinstance(candles[i], list) and candles[i] else None
            if not isinstance(prev_ts, (int, float)) or not isinstance(curr_ts, (int, float)):
                continue
            delta = int(curr_ts) - int(prev_ts)
            if delta <= 0:
                quality_flags.append("missing_candle")
                break
            if delta > expected_step_ms * 1.5:
                quality_flags.append("gap")
                break

        now_dt = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
        close_dt = datetime.fromtimestamp((source_ts_ms / 1000) + TIMEFRAME_SECONDS[timeframe], tz=timezone.utc)
        stale = (now_dt - close_dt).total_seconds() > STALE_THRESHOLDS_SECONDS[timeframe]
        if stale:
            quality_flags.append("stale")

        flags = list(dict.fromkeys(quality_flags))
        return MarketDataSnapshot(
            provider_id=self.provider_id,
            retrieved_at=retrieved_at,
            source_timestamp=source_timestamp,
            staleness_flag=stale,
            quality_flags=flags,
            asset=asset,
            price=price,
            candles=candles,
        )

    def fetch(self, asset: str) -> MarketDataSnapshot:
        return self.get_ohlcv(asset=asset, timeframe="1m", limit=50)
