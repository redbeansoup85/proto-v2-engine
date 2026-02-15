from __future__ import annotations

import json
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List

from sentinel_domain.adapters.market.bybit_rest import fetch_raw_market_bundle
from sentinel_domain.features.indicators import compute_tf_indicators
from sentinel_domain.features.snapshot_builder import SNAPSHOT_TEMPLATE, make_template_snapshot
import sentinel_domain.services.snapshot_service as snapshot_service
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


def _lsr_fixture() -> Dict[str, Any]:
    return {
        "retCode": 0,
        "retMsg": "OK",
        "result": {
            "category": "linear",
            "symbol": "BTCUSDT",
            "list": [{"symbol": "BTCUSDT", "buyRatio": "0.53", "sellRatio": "0.47", "timestamp": "1672051897447"}],
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
    if "/v5/market/account-ratio" in url:
        return _lsr_fixture()
    raise AssertionError("unexpected_url:%s" % url)


def _http_fixture_zero_volume(url: str, timeout_sec: float) -> Dict[str, Any]:
    if "/v5/market/kline" in url:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        interval = (q.get("interval") or ["15"])[0]
        now_ms = int(time.time() * 1000) - (300 * 60 * 1000)
        interval_min = int(interval)
        payload = _mk_bybit_kline_payload(interval_minutes=interval_min, count=260, start_ms=now_ms)
        rows = (((payload.get("result") or {}).get("list")) or [])
        for row in rows:
            if isinstance(row, list) and len(row) > 5:
                row[5] = "0"
        return payload
    return _http_fixture_router(url, timeout_sec)


def _http_fixture_15m_short(url: str, timeout_sec: float) -> Dict[str, Any]:
    if "/v5/market/kline" in url:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        interval = (q.get("interval") or ["15"])[0]
        now_ms = int(time.time() * 1000) - (300 * 60 * 1000)
        interval_min = int(interval)
        count = 10 if interval == "15" else 260
        return _mk_bybit_kline_payload(interval_minutes=interval_min, count=count, start_ms=now_ms)
    return _http_fixture_router(url, timeout_sec)


def _http_fixture_15m_empty(url: str, timeout_sec: float) -> Dict[str, Any]:
    if "/v5/market/kline" in url:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        interval = (q.get("interval") or ["15"])[0]
        if interval == "15":
            return {"retCode": 0, "retMsg": "OK", "result": {"list": []}}
    return _http_fixture_router(url, timeout_sec)


def _http_fixture_15m_stale(url: str, timeout_sec: float) -> Dict[str, Any]:
    if "/v5/market/kline" in url:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        interval = (q.get("interval") or ["15"])[0]
        interval_min = int(interval)
        if interval == "15":
            return _mk_bybit_kline_payload(interval_minutes=interval_min, count=260, start_ms=0)
        now_ms = int(time.time() * 1000) - (300 * 60 * 1000)
        return _mk_bybit_kline_payload(interval_minutes=interval_min, count=260, start_ms=now_ms)
    return _http_fixture_router(url, timeout_sec)


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
        if "/v5/market/account-ratio" in url:
            return _lsr_fixture()
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
        if "/v5/market/account-ratio" in url:
            return _lsr_fixture()
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
    assert isinstance(written["tf_state"]["15m"]["vwap"], float)
    assert isinstance(written["tf_state"]["15m"]["price"], float)
    assert isinstance(written["deriv"]["oi"], float)
    assert isinstance(written["deriv"]["funding"], float)
    assert isinstance(written["deriv"]["lsr"], float)
    assert isinstance(written["deriv"]["cvd_proxy"]["futures"], float)


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


def test_fail_closed_lsr_keeps_na(tmp_path: Path) -> None:
    def _http_lsr_error(url: str, timeout_sec: float) -> Dict[str, Any]:
        if "/v5/market/account-ratio" in url:
            raise RuntimeError("lsr-error")
        return _http_fixture_router(url, timeout_sec)

    ref = capture_market_snapshot(
        asset="BTCUSDT",
        ts_utc="2026-02-15T12:00:00Z",
        snap_dir=tmp_path,
        snap_id="SNAP-LSR-ERR",
        venue="bybit",
        market_type="perp",
        tfs=["1m", "5m", "15m", "1h", "4h"],
        stale_limit_ms=10_000_000_000,
        http_get_json=_http_lsr_error,
    )
    written = json.loads((tmp_path / Path(ref).name).read_text(encoding="utf-8"))
    assert written["deriv"]["lsr"] == "n/a"


def test_deriv_guard_non_perp_keeps_na_and_sets_error() -> None:
    ts_utc = "2026-02-15T12:00:00Z"
    snapshot, _, evidence = build_snapshot_payload(
        asset="BTCUSDT",
        ts_utc=ts_utc,
        venue="bybit",
        market_type="spot",
        tfs=["1m", "5m", "15m", "1h", "4h"],
        stale_limit_ms=10_000_000_000,
        http_get_json=_http_fixture_router,
    )

    assert snapshot["deriv"]["oi"] == "n/a"
    assert snapshot["deriv"]["funding"] == "n/a"
    assert snapshot["deriv"]["lsr"] == "n/a"
    assert any(
        isinstance(err, dict) and err.get("type") == "unsupported_deriv_market_type"
        for err in evidence.get("proof_errors", [])
    )


def test_fail_closed_vwap_keeps_na_on_zero_volume(tmp_path: Path) -> None:
    ref = capture_market_snapshot(
        asset="BTCUSDT",
        ts_utc="2026-02-15T12:00:00Z",
        snap_dir=tmp_path,
        snap_id="SNAP-VWAP-ERR",
        venue="bybit",
        market_type="perp",
        tfs=["1m", "5m", "15m", "1h", "4h"],
        stale_limit_ms=10_000_000_000,
        http_get_json=_http_fixture_zero_volume,
    )
    written = json.loads((tmp_path / Path(ref).name).read_text(encoding="utf-8"))
    assert written["tf_state"]["15m"]["vwap"] == "n/a"


def test_fail_closed_cvd_proxy_futures_keeps_na_on_short_15m(tmp_path: Path) -> None:
    ref = capture_market_snapshot(
        asset="BTCUSDT",
        ts_utc="2026-02-15T12:00:00Z",
        snap_dir=tmp_path,
        snap_id="SNAP-CVD-ERR",
        venue="bybit",
        market_type="perp",
        tfs=["1m", "5m", "15m", "1h", "4h"],
        stale_limit_ms=10_000_000_000,
        http_get_json=_http_fixture_15m_short,
    )
    written = json.loads((tmp_path / Path(ref).name).read_text(encoding="utf-8"))
    assert written["deriv"]["cvd_proxy"]["futures"] == "n/a"


def test_fail_closed_price_keeps_na_on_empty_15m(tmp_path: Path) -> None:
    ref = capture_market_snapshot(
        asset="BTCUSDT",
        ts_utc="2026-02-15T12:00:00Z",
        snap_dir=tmp_path,
        snap_id="SNAP-PRICE-ERR",
        venue="bybit",
        market_type="perp",
        tfs=["1m", "5m", "15m", "1h", "4h"],
        stale_limit_ms=10_000_000_000,
        http_get_json=_http_fixture_15m_empty,
    )
    written = json.loads((tmp_path / Path(ref).name).read_text(encoding="utf-8"))
    assert written["tf_state"]["15m"]["price"] == "n/a"


def test_stale_guard_15m_keeps_na_and_marks_missing(tmp_path: Path) -> None:
    ts_utc = "2026-02-15T12:00:00Z"
    ref = capture_market_snapshot(
        asset="BTCUSDT",
        ts_utc=ts_utc,
        snap_dir=tmp_path,
        snap_id="SNAP-STALE-15M",
        venue="bybit",
        market_type="perp",
        tfs=["1m", "5m", "15m", "1h", "4h"],
        stale_limit_ms=60 * 60 * 1000,
        http_get_json=_http_fixture_15m_stale,
    )
    written = json.loads((tmp_path / Path(ref).name).read_text(encoding="utf-8"))
    assert written["tf_state"]["15m"]["vwap"] == "n/a"
    assert written["tf_state"]["15m"]["price"] == "n/a"

    _, _, evidence = build_snapshot_payload(
        asset="BTCUSDT",
        ts_utc=ts_utc,
        venue="bybit",
        market_type="perp",
        tfs=["1m", "5m", "15m", "1h", "4h"],
        stale_limit_ms=60 * 60 * 1000,
        http_get_json=_http_fixture_15m_stale,
    )
    assert "candles.15m.stale" in evidence["missing"]


def test_stale_default_applied_when_limit_nonpositive() -> None:
    ts_utc = "2026-02-15T12:00:00Z"
    snapshot, _, evidence = build_snapshot_payload(
        asset="BTCUSDT",
        ts_utc=ts_utc,
        venue="bybit",
        market_type="perp",
        tfs=["15m"],
        stale_limit_ms=0,
        http_get_json=_http_fixture_15m_stale,
    )
    assert snapshot["tf_state"]["15m"]["vwap"] == "n/a"
    assert snapshot["tf_state"]["15m"]["price"] == "n/a"
    assert "candles.15m.stale" in evidence["missing"]
    assert any(
        isinstance(err, dict) and err.get("type") == "stale_limit_default_applied"
        for err in evidence.get("proof_errors", [])
    )


def test_stale_env_parse_error_recorded_and_default_applied(tmp_path: Path, monkeypatch) -> None:
    ts_utc = "2026-02-15T12:00:00Z"
    monkeypatch.setenv("SENTINEL_STALE_MS", "abc")

    ref = capture_market_snapshot(
        asset="BTCUSDT",
        ts_utc=ts_utc,
        snap_dir=tmp_path,
        snap_id="SNAP-STALE-ENV-PARSE",
        venue="bybit",
        market_type="perp",
        tfs=["15m"],
        stale_limit_ms=None,
        http_get_json=_http_fixture_15m_stale,
    )
    written = json.loads((tmp_path / Path(ref).name).read_text(encoding="utf-8"))
    assert written["tf_state"]["15m"]["vwap"] == "n/a"
    assert written["tf_state"]["15m"]["price"] == "n/a"

    _, _, evidence = build_snapshot_payload(
        asset="BTCUSDT",
        ts_utc=ts_utc,
        venue="bybit",
        market_type="perp",
        tfs=["15m"],
        stale_limit_ms=None,
        stale_limit_parse_error="invalid_int:abc",
        http_get_json=_http_fixture_15m_stale,
    )
    assert "candles.15m.stale" in evidence["missing"]
    assert any(
        isinstance(err, dict) and err.get("type") == "stale_limit_env_parse_error"
        for err in evidence.get("proof_errors", [])
    )
    assert any(
        isinstance(err, dict) and err.get("type") == "stale_limit_default_applied"
        for err in evidence.get("proof_errors", [])
    )


def test_proof_errors_schema_normalized_v1(monkeypatch) -> None:
    def _fake_raw_bundle(**_: Any) -> Dict[str, Any]:
        return {
            "schema": "raw_market_bundle.v1",
            "venue": "bybit",
            "market_type": "perp",
            "asset": "BTCUSDT",
            "ts_utc": "2026-02-15T12:00:00Z",
            "candles": {"15m": [{"t": "0", "o": 1.0, "h": 1.0, "l": 1.0, "c": 1.0, "v": 1.0}]},
            "deriv": {"oi": None, "funding": None, "lsr": None},
            "proof": {
                "source": "rest",
                "endpoints": [],
                "latency_ms": 1,
                "errors": [
                    "oops",
                    {"type": "legacy_error", "value_ms": 123},
                ],
            },
        }

    monkeypatch.setattr(snapshot_service, "fetch_raw_market_bundle", _fake_raw_bundle)
    _, _, evidence = build_snapshot_payload(
        asset="BTCUSDT",
        ts_utc="2026-02-15T12:00:00Z",
        venue="bybit",
        market_type="perp",
        tfs=["15m"],
        stale_limit_ms=None,
        stale_limit_parse_error="invalid_int:abc",
    )

    for err in evidence["proof_errors"]:
        assert isinstance(err, dict)
        assert isinstance(err.get("type"), str) and bool(err["type"])
        assert err.get("severity") in ("warn", "error")

    stale_default = next(err for err in evidence["proof_errors"] if err.get("type") == "stale_limit_default_applied")
    assert stale_default.get("severity") == "warn"
    assert "value_ms" not in stale_default
    assert isinstance(stale_default.get("meta"), dict) and "value_ms" in stale_default["meta"]

    stale_parse = next(err for err in evidence["proof_errors"] if err.get("type") == "stale_limit_env_parse_error")
    assert stale_parse.get("severity") == "error"

    unknown = next(err for err in evidence["proof_errors"] if err.get("type") == "unknown_proof_error")
    assert unknown.get("severity") == "error"
    assert isinstance(unknown.get("meta"), dict)
    assert "raw" in unknown["meta"]
