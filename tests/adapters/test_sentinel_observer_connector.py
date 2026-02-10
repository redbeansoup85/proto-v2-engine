from __future__ import annotations

from pathlib import Path

import pytest

import adapters.sentinel_observer_connector as connector


class _DummyProvider:
    provider_id = "ccxt:binance"


def _wire_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    obs = tmp_path / "var/observer/sentinel/intent_events.jsonl"
    chain = tmp_path / "var/audit/sentinel/simulation_chain.jsonl"
    monkeypatch.setattr(connector, "OBSERVER_EVENTS_PATH", obs)
    monkeypatch.setattr(connector, "SIM_CHAIN_PATH", chain)
    monkeypatch.setattr(connector, "_ensure_output_paths", lambda: (obs, chain))
    return obs, chain


def test_no_execute_enforced_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _wire_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(connector, "_build_provider", lambda provider, timeframe: _DummyProvider())
    monkeypatch.setattr(
        connector,
        "_run_pipeline",
        lambda **kwargs: {
            "schema_version": "sentinel_trade_intent.v1",
            "no_execute": False,
            "quality": {"staleness_flag": False, "quality_flags": []},
        },
    )
    with pytest.raises(RuntimeError, match="EXECUTION_NOT_ALLOWED"):
        connector.run_sentinel_simulation_connector(asset="BTC/USDT", timeframe="1m", provider="ccxt")


def test_stale_data_forces_flat_and_hold_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _wire_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(connector, "_build_provider", lambda provider, timeframe: _DummyProvider())
    monkeypatch.setattr(
        connector,
        "_run_pipeline",
        lambda **kwargs: {
            "schema_version": "sentinel_trade_intent.v1",
            "intent_id": "SINTENT-TEST",
            "side": "LONG",
            "no_execute": True,
            "quality": {"staleness_flag": True, "quality_flags": ["stale"]},
        },
    )

    out = connector.run_sentinel_simulation_connector(asset="BTC/USDT", timeframe="1m", provider="ccxt")
    assert out["side"] == "FLAT"
    assert out["no_execute"] is True
    assert "STALE_DATA_HOLD" in out["hold_reason"]
    assert "QUALITY_DEGRADED" in out["hold_reason"]


def test_output_paths_are_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(connector, "OBSERVER_EVENTS_PATH", Path("/tmp/observer.jsonl"))
    with pytest.raises(RuntimeError, match="INVALID_OUTPUT_PATH"):
        connector.run_sentinel_simulation_connector(asset="BTC/USDT", timeframe="1m", provider="ccxt")
