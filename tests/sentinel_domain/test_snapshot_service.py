from __future__ import annotations

import json
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List

from sentinel_domain.adapters.market.bybit_rest import fetch_raw_market_bundle
from sentinel_domain.features.indicators import compute_tf_indicators
from sentinel_domain.features.snapshot_builder import SNAPSHOT_TEMPLATE, make_template_snapshot
from sentinel_domain.services.snapshot_service import build_snapshot_payload, capture_market_snapshot


def _mk_bybit_kline_payload(interval_minutes: int, count: int, start_ms: int) -> Dict[str, Any]:
    # Bybit returns kline list in reverse chronological order.
    rows: List[List[str]] = []
    price = 100.0
    step_ms = interval_minutes * 60 * 1000
    for i in range(count):
        ts_ms = start_ms + (i * step_ms)
        close = price + (i * 0.5)
        open_p = close - 0.2
        high = close + 0.3
        low = close - 0.4
        vol = 10.0 + i
        rows.append(
            [
                str(ts_ms),
                str(open_p),
                str(high),
                str(low),
                str(close),
                str(vol),
                "0",
            ]
        )
    rows.reverse()
    return {"retCode": 0, "retMsg": "OK", "result": {"list": rows}}


def _open_interest_fixture() -> Dict[str, Any]:
    return {
        "retCode": 0,
        "retMsg": "OK",
        "result": {
            "symbol": "BTCUSDT",
            "category": "linear",
            "list": [{"openInterest": "461134384.00000000", "timestamp": "1669571400000"}],
            "nextPageCursor": "",
        },
        "time": 1672053548579,
    }


def _funding_history_fixture() -> Dict[str, Any]:
    return {
        "retCode": 0,
        "retMsg": "OK",
        "result": {
            "category": "linear",
            "list": [{"symbol": "BTCPERP", "fundingRate": "0.0001", "fundingRateTimestamp": "1672041600000"}],
        },
        "time": 1672051897447,
    }


def _http_fixture_router(url: str, timeout_sec: float) -> Dict[str, Any]:
    _ = timeout_sec
    if "/v5/market/kline" in url:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        interval = (q.get("interval") or ["15"])[0]
        now_ms = int(time.time() * 1000) - (300 * 60 * 1000)
        interval_min = int(interval)
        return _mk_bybit_kline_payload(interval_minutes=interval_min, count=260, start_ms=now_ms)
    if "/v5/market/open-interest" in url:
        return _open_interest_fixture()
    if "/v5/market/funding/history" in url:
        return _funding_history_fixture()
    raise AssertionError("unexpected_url:%s" % url)


def test_adapter_parses_fixture_candles_ascending_and_numeric() -> None:
    raw = fetch_raw_market_bundle(
        asset="BTCUSDT",
        tfs=["15m"],
        market_type="perp",
        http_get_json=_http_fixture_router,
    )
    candles_15m = raw["candles"]["15m"]
    assert candles_15m
    first = candles_15m[0]
    assert isinstance(first["t"], str)
    assert isinstance(first["o"], float)
    assert isinstance(first["h"], float)
    assert isinstance(first["l"], float)
    assert isinstance(first["c"], float)
    assert isinstance(first["v"], float)


def test_indicators_compute_numeric_with_sufficient_closes() -> None:
    raw = fetch_raw_market_bundle(
        asset="BTCUSDT",
        tfs=["15m"],
        market_type="perp",
        http_get_json=_http_fixture_router,
    )
    per_tf = compute_tf_indicators(raw["candles"])
    metrics = per_tf["15m"]
    assert isinstance(metrics["ema20"], float)
    assert isinstance(metrics["rsi14"], float)


def test_fail_closed_evidence_when_missing_or_proof_errors() -> None:
    def _http_missing_4h(url: str, timeout_sec: float) -> Dict[str, Any]:
        if "/v5/market/open-interest" in url:
            return _open_interest_fixture()
        if "/v5/market/funding/history" in url:
            return _funding_history_fixture()
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        interval = (q.get("interval") or ["15"])[0]
        if interval == "240":
            return {"retCode": 0, "retMsg": "OK", "result": {"list": []}}
        return _http_fixture_router(url, timeout_sec)

    ts_utc = "2026-02-15T12:00:00Z"
    _, _, evidence = build_snapshot_payload(
        asset="BTCUSDT",
        ts_utc=ts_utc,
        venue="bybit",
        market_type="perp",
        tfs=["1m", "5m", "15m", "1h", "4h"],
        stale_limit_ms=10_000_000_000,
        http_get_json=_http_missing_4h,
    )
    assert evidence["ok"] is False
    assert "candles.4h" in evidence["missing"]

    def _http_raises(url: str, timeout_sec: float) -> Dict[str, Any]:
        if "/v5/market/open-interest" in url:
            return _open_interest_fixture()
        if "/v5/market/funding/history" in url:
            return _funding_history_fixture()
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        interval = (q.get("interval") or ["15"])[0]
        if interval == "240":
            raise RuntimeError("fixture-error")
        return _http_fixture_router(url, timeout_sec)

    _, _, evidence_2 = build_snapshot_payload(
        asset="BTCUSDT",
        ts_utc=ts_utc,
        venue="bybit",
        market_type="perp",
        tfs=["1m", "5m", "15m", "1h", "4h"],
        stale_limit_ms=10_000_000_000,
        http_get_json=_http_raises,
    )
    assert evidence_2["ok"] is False
    assert evidence_2["proof_errors"]


def test_snapshot_service_atomic_write_and_template_shape_lock(tmp_path: Path) -> None:
    snap_dir = tmp_path / "snapshots"
    ts_utc = "2026-02-15T12:00:00Z"

    ref = capture_market_snapshot(
        asset="BTCUSDT",
        ts_utc=ts_utc,
        snap_dir=snap_dir,
        snap_id="SNAP-TEST000001",
        venue="bybit",
        market_type="perp",
        tfs=["1m", "5m", "15m", "1h", "4h"],
        stale_limit_ms=10_000_000_000,
        http_get_json=_http_fixture_router,
    )

    out_path = snap_dir / Path(ref).name
    assert out_path.exists()
    tmp_leftovers = list(snap_dir.glob("*.tmp.*"))
    assert not tmp_leftovers

    written = json.loads(out_path.read_text(encoding="utf-8"))
    template = make_template_snapshot(asset="BTCUSDT", ts_utc=ts_utc)
    assert set(written.keys()) == set(template.keys()) == set(SNAPSHOT_TEMPLATE.keys())
    assert set(written.keys()) == {"schema", "asset", "ts_utc", "tf_state", "deriv"}
    assert set(written["deriv"].keys()) == {"oi", "funding", "lsr", "cvd_proxy"}

    assert isinstance(written["tf_state"]["15m"]["ema20"], float)
    assert isinstance(written["tf_state"]["15m"]["ema50"], float)
    assert isinstance(written["tf_state"]["15m"]["ema200"], float)
    assert isinstance(written["tf_state"]["15m"]["rsi"], float)
    assert isinstance(written["deriv"]["oi"], float)
    assert isinstance(written["deriv"]["funding"], float)


def test_fail_closed_oi_keeps_na(tmp_path: Path) -> None:
    def _http_oi_error(url: str, timeout_sec: float) -> Dict[str, Any]:
        if "/v5/market/open-interest" in url:
            raise RuntimeError("oi-error")
        return _http_fixture_router(url, timeout_sec)

    ref = capture_market_snapshot(
        asset="BTCUSDT",
        ts_utc="2026-02-15T12:00:00Z",
        snap_dir=tmp_path,
        snap_id="SNAP-OI-ERR",
        venue="bybit",
        market_type="perp",
        tfs=["1m", "5m", "15m", "1h", "4h"],
        stale_limit_ms=10_000_000_000,
        http_get_json=_http_oi_error,
    )
    written = json.loads((tmp_path / Path(ref).name).read_text(encoding="utf-8"))
    assert written["deriv"]["oi"] == "n/a"


def test_fail_closed_funding_keeps_na(tmp_path: Path) -> None:
    def _http_funding_error(url: str, timeout_sec: float) -> Dict[str, Any]:
        if "/v5/market/funding/history" in url:
            raise RuntimeError("funding-error")
        return _http_fixture_router(url, timeout_sec)

    ref = capture_market_snapshot(
        asset="BTCUSDT",
        ts_utc="2026-02-15T12:00:00Z",
        snap_dir=tmp_path,
        snap_id="SNAP-FUNDING-ERR",
        venue="bybit",
        market_type="perp",
        tfs=["1m", "5m", "15m", "1h", "4h"],
        stale_limit_ms=10_000_000_000,
        http_get_json=_http_funding_error,
    )
    written = json.loads((tmp_path / Path(ref).name).read_text(encoding="utf-8"))
    assert written["deriv"]["funding"] == "n/a"
