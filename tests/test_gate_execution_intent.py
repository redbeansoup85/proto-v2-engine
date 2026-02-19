from __future__ import annotations

from tools.gates.gate_execution_intent import validate_intent


def _intent() -> dict:
    return {
        "run_id": "RUN-INTENT-001",
        "ts_utc": "2026-02-19T00:00:00Z",
        "symbol": "SOLUSDT",
        "side": "BUY",
        "order_type": "MARKET",
        "qty": 1.0,
        "mode": "LIVE",
        "risk": {
            "max_qty": 1.0,
            "max_notional_usd": 100.0,
        },
        "evidence": {
            "decision_reason": "ok",
            "plan_mode": "LIVE",
        },
    }


def test_valid_market_only_live_passes() -> None:
    assert validate_intent(_intent()) == []


def test_rejects_non_market() -> None:
    intent = _intent()
    intent["order_type"] = "LIMIT"
    violations = validate_intent(intent)
    assert any(v["reason"] == "order_type_must_be_market" for v in violations)
