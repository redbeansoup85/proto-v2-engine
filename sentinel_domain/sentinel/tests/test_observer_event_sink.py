from __future__ import annotations

import json
from pathlib import Path

import pytest

from sentinel.adapter.observer_event_sink import EVENT_SCHEMA_ID, append_intent_event, canonical_intent_hash
from sentinel.feeds.base import MarketDataSnapshot
from sentinel.tracks.simulation.pipeline import run_simulation_pipeline


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


def test_event_written_once(tmp_path: Path) -> None:
    out_path = tmp_path / "simulation_events.jsonl"
    chain_path = tmp_path / "simulation_chain.jsonl"
    event = {"asset": "BTC/USDT", "side": "LONG", "summary": "signal", "timeframe": "1m"}

    run_simulation_pipeline(
        observer_event=event,
        provider=_FreshProvider(),
        audit_events_path=out_path,
        audit_chain_path=chain_path,
    )

    sink_path = tmp_path / "intent_events.jsonl"
    assert sink_path.exists()
    rows = [json.loads(x) for x in sink_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(rows) == 1
    assert rows[0]["schema_id"] == EVENT_SCHEMA_ID


def test_forbidden_intent_never_written(tmp_path: Path) -> None:
    sink_path = tmp_path / "intent_events.jsonl"
    bad_intent = _valid_intent()
    bad_intent["nested"] = {"broker": "x"}
    event = {
        "event_id": "evt_test",
        "schema_id": EVENT_SCHEMA_ID,
        "source": "sentinel.simulation.pipeline",
        "track": "SIMULATION",
        "asset": "BTC/USDT",
        "timeframe": "1m",
        "intent": bad_intent,
        "quality": bad_intent["quality"],
        "ts": bad_intent["created_at"],
    }

    with pytest.raises(RuntimeError, match="forbidden keys"):
        append_intent_event(event, path=str(sink_path))

    if sink_path.exists():
        assert sink_path.read_text(encoding="utf-8") == ""


def test_replay_produces_same_intent_hash() -> None:
    intent_a = _valid_intent()
    intent_b = json.loads(json.dumps(intent_a, sort_keys=True))

    h1 = canonical_intent_hash(intent_a)
    h2 = canonical_intent_hash(intent_b)

    assert h1 == h2
