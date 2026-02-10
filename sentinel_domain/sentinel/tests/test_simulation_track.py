from __future__ import annotations

import json
from pathlib import Path

import pytest

from domains.sentinel.feeds.base import MarketDataSnapshot
from domains.sentinel.tracks.simulation.pipeline import run_simulation_pipeline
from domains.sentinel.tracks.simulation.validators import validate_simulation_intent


class _FreshProvider:
    provider_id = "fresh_provider"

    def fetch(self, asset: str) -> MarketDataSnapshot:
        return MarketDataSnapshot(
            provider_id=self.provider_id,
            retrieved_at="2026-02-10T00:00:00Z",
            source_timestamp="2026-02-10T00:00:00Z",
            staleness_flag=False,
            quality_flags=[],
            asset=asset,
            price=123.4,
        )


class _StaleProvider:
    provider_id = "stale_provider"

    def fetch(self, asset: str) -> MarketDataSnapshot:
        return MarketDataSnapshot(
            provider_id=self.provider_id,
            retrieved_at="2026-02-10T00:10:00Z",
            source_timestamp="2026-02-10T00:00:00Z",
            staleness_flag=True,
            quality_flags=["STALE_DATA"],
            asset=asset,
            price=None,
        )


def test_forbidden_keys_in_simulation_fail_closed() -> None:
    payload = {
        "track_id": "SIMULATION",
        "no_execute": True,
        "nested": {"place_order": "x"},
    }
    with pytest.raises(RuntimeError, match="forbidden keys"):
        validate_simulation_intent(payload)


def test_no_execute_false_in_simulation_fail_closed() -> None:
    payload = {
        "track_id": "SIMULATION",
        "no_execute": False,
        "quality": {"staleness_flag": False, "quality_flags": []},
    }
    with pytest.raises(RuntimeError, match="no_execute"):
        validate_simulation_intent(payload)


def test_staleness_triggers_hold_and_logs_flag(tmp_path: Path) -> None:
    event = {"asset": "BTCUSDT", "side": "LONG", "summary": "signal"}
    out_path = tmp_path / "events.jsonl"
    chain_path = tmp_path / "chain.jsonl"

    intent = run_simulation_pipeline(
        observer_event=event,
        provider=_StaleProvider(),
        audit_events_path=out_path,
        audit_chain_path=chain_path,
    )

    assert intent["side"] == "FLAT"
    assert "STALE_DATA_HOLD" in intent["quality"]["quality_flags"]
    assert out_path.exists()
    assert chain_path.exists()
    rows = [json.loads(x) for x in out_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(rows) == 1
