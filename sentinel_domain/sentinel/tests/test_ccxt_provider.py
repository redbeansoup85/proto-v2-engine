from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sentinel.feeds.ccxt_provider import CCXTProvider


class _FakeExchange:
    def __init__(self, candles, *, fail_mode: str | None = None) -> None:
        self.markets = {"BTC/USDT": {"id": "BTCUSDT"}}
        self.timeframes = {"1m": "1m", "5m": "5m"}
        self._candles = candles
        self._fail_mode = fail_mode
        self.calls = 0

    def load_markets(self):
        return self.markets

    def fetch_ohlcv(self, _asset, timeframe="1m", limit=50):
        self.calls += 1
        if self._fail_mode == "rate_limit":
            raise RuntimeError("429 Too Many Requests")
        if self._fail_mode == "exchange_error":
            raise RuntimeError("exchange unavailable")
        return self._candles[:limit]


def _old_candle_ms(seconds_ago: int) -> int:
    ts = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    return int(ts.timestamp() * 1000)


def test_ccxt_provider_stale_sets_flag_and_quality() -> None:
    # 1m timeframe stale threshold is 120s, close time adds +60s; 500s ago is stale.
    candles = [[_old_candle_ms(500), 1.0, 1.0, 1.0, 1.0, 100.0]]
    ex = _FakeExchange(candles)
    provider = CCXTProvider(exchange_factory=lambda: ex, sleep_fn=lambda _s: None)
    snap = provider.get_ohlcv(asset="BTC/USDT", timeframe="1m", limit=1)
    assert snap.staleness_flag is True
    assert "stale" in [x.lower() for x in snap.quality_flags]
    assert snap.provider_id == "ccxt:binance"


def test_ccxt_provider_rate_limit_marks_quality_nonfatal() -> None:
    ex = _FakeExchange([], fail_mode="rate_limit")
    provider = CCXTProvider(exchange_factory=lambda: ex, sleep_fn=lambda _s: None)
    snap = provider.get_ohlcv(asset="BTC/USDT", timeframe="1m", limit=1)
    flags = [x.lower() for x in snap.quality_flags]
    assert snap.staleness_flag is True
    assert "rate_limited" in flags
