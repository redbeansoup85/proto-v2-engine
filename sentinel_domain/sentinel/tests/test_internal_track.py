from __future__ import annotations

import pytest

from sentinel.analyzer.internal_guard import analyzer_create_internal_exec_intent
from sentinel.tracks.internal.brokers import execute_paper_broker
from sentinel.tracks.internal.exec_gate import IdempotencyStore, create_internal_exec_intent


def _internal_source_intent() -> dict:
    return {
        "schema_version": "sentinel_trade_intent.v1",
        "intent_id": "SINTENT-ABCDEFGH",
        "track_id": "INTERNAL",
        "mode": "DRY_RUN",
        "producer": {"domain": "sentinel", "component": "observer_adapter"},
        "asset": "BTCUSDT",
        "side": "FLAT",
        "analysis_summary": "internal routing candidate",
        "quality": {
            "provider_id": "x",
            "retrieved_at": "2026-02-10T00:00:00Z",
            "source_timestamp": "2026-02-10T00:00:00Z",
            "staleness_flag": False,
            "quality_flags": [],
        },
        "no_execute": True,
        "created_at": "2026-02-10T00:00:00Z",
    }


def test_analyzer_cannot_create_internal_exec_intent() -> None:
    with pytest.raises(RuntimeError, match="analyzer cannot create internal_exec_intent"):
        analyzer_create_internal_exec_intent(_internal_source_intent())


def test_real_without_approval_fails() -> None:
    store = IdempotencyStore()
    with pytest.raises(RuntimeError, match="approval required for real mode"):
        create_internal_exec_intent(
            sentinel_trade_intent=_internal_source_intent(),
            mode="real",
            idempotency_key="idem-0001",
            approval_id=None,
            producer_component="exec_gate",
            idempotency_store=store,
        )


def test_paper_allowed() -> None:
    store = IdempotencyStore()
    intent = create_internal_exec_intent(
        sentinel_trade_intent=_internal_source_intent(),
        mode="paper",
        idempotency_key="idem-0002",
        approval_id=None,
        producer_component="exec_gate",
        idempotency_store=store,
    )
    receipt = execute_paper_broker(intent)
    assert receipt["status"] == "accepted"
    assert receipt["broker"] == "paper"


def test_idempotency_dedupe() -> None:
    store = IdempotencyStore()
    kwargs = dict(
        sentinel_trade_intent=_internal_source_intent(),
        mode="paper",
        idempotency_key="idem-dup-001",
        approval_id=None,
        producer_component="exec_gate",
        idempotency_store=store,
    )
    _ = create_internal_exec_intent(**kwargs)
    with pytest.raises(RuntimeError, match="duplicate idempotency_key"):
        create_internal_exec_intent(**kwargs)


def test_internal_exec_gate_stale_quality_returns_hold_flat() -> None:
    store = IdempotencyStore()
    src = _internal_source_intent()
    src["side"] = "LONG"
    src["quality"]["staleness_flag"] = True
    src["quality"]["quality_flags"] = ["stale"]
    result = create_internal_exec_intent(
        sentinel_trade_intent=src,
        mode="paper",
        idempotency_key="idem-stale-001",
        approval_id=None,
        producer_component="exec_gate",
        idempotency_store=store,
    )
    assert result["schema_version"] == "sentinel_trade_intent.v1"
    assert result["side"] == "FLAT"
    assert result["no_execute"] is True
    flags = [str(x) for x in result["quality"]["quality_flags"]]
    assert "STALE_DATA_HOLD" in flags
    assert "INTERNAL_EXEC_BLOCKED_QUALITY" in flags
