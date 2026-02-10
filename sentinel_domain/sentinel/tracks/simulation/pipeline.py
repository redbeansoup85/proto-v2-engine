from __future__ import annotations

from pathlib import Path
from typing import Any

from sentinel.adapter.observer_adapter import observer_event_to_trade_intent
from sentinel.adapter.observer_event_sink import EVENT_SCHEMA_ID, append_intent_event
from sentinel.feeds.base import MarketDataProvider
from sentinel.tracks.simulation.audit_writer import append_simulation_audit
from sentinel.tracks.simulation.validators import enforce_conservative_behavior, validate_simulation_intent


def run_simulation_pipeline(
    *,
    observer_event: dict[str, Any],
    provider: MarketDataProvider,
    audit_events_path: Path,
    audit_chain_path: Path,
) -> dict[str, Any]:
    intent, _snapshot = observer_event_to_trade_intent(
        observer_event=observer_event,
        provider=provider,
        track_id="SIMULATION",
    )
    validate_simulation_intent(intent)
    intent = enforce_conservative_behavior(intent)
    validate_simulation_intent(intent)
    append_intent_event(
        {
            "event_id": f"evt_{intent['intent_id']}",
            "schema_id": EVENT_SCHEMA_ID,
            "source": "sentinel.simulation.pipeline",
            "track": intent["track_id"],
            "asset": intent["asset"],
            "timeframe": str(observer_event.get("timeframe", "unknown")),
            "intent": intent,
            "quality": intent["quality"],
            "ts": intent["created_at"],
        },
        path=str(audit_events_path.parent / "intent_events.jsonl"),
    )
    append_simulation_audit(intent=intent, out_path=audit_events_path, chain_path=audit_chain_path)
    return intent
