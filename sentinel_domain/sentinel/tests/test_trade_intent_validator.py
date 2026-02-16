from __future__ import annotations

import pytest

from sentinel.tracks.simulation.validators import validate_trade_intent


def _valid_intent() -> dict:
    return {
        "schema_version": "sentinel_trade_intent.v1",
        "intent_id": "INTENT-12345678",
        "track_id": "SIMULATION",
        "mode": "DRY_RUN",
        "producer": {"domain": "sentinel", "component": "simulation"},
        "asset": "BTC/USDT",
        "side": "FLAT",
        "analysis_summary": "quality hold",
        "quality": {
            "provider_id": "ccxt:binance",
            "retrieved_at": "2026-02-10T00:00:00Z",
            "source_timestamp": "2026-02-10T00:00:00Z",
            "staleness_flag": False,
            "quality_flags": [],
        },
        "no_execute": True,
        "created_at": "2026-02-10T00:00:00Z",
    }


def test_valid_intent_passes() -> None:
    intent = _valid_intent()
    out = validate_trade_intent(intent)
    assert out is intent


def test_no_execute_false_fails() -> None:
    intent = _valid_intent()
    intent["no_execute"] = False
    with pytest.raises(RuntimeError, match="no_execute"):
        validate_trade_intent(intent)


def test_forbidden_key_top_level_fails() -> None:
    intent = _valid_intent()
    intent["price"] = 100.0
    with pytest.raises(RuntimeError, match="forbidden keys"):
        validate_trade_intent(intent)


def test_forbidden_key_nested_fails() -> None:
    intent = _valid_intent()
    intent["meta"] = {"nested": {"api_key": "x"}}
    with pytest.raises(RuntimeError, match="forbidden keys"):
        validate_trade_intent(intent)
