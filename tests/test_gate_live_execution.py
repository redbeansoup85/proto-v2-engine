from __future__ import annotations

from tools.gates.gate_live_execution import validate_live


def _intent() -> dict:
    return {
        "run_id": "RUN-LIVE-001",
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


def test_valid_market_only_live_passes_with_price() -> None:
    assert validate_live(_intent(), last_price_usd=50.0) == []


def test_rejects_missing_price_notional_cap() -> None:
    violations = validate_live(_intent(), last_price_usd=None)
    assert any(v["reason"] == "missing_price_for_notional_cap" for v in violations)


def test_rejects_qty_over_max_qty() -> None:
    intent = _intent()
    intent["qty"] = 2.0
    violations = validate_live(intent, last_price_usd=50.0)
    assert any(v["reason"] == "qty_exceeds_max_qty" for v in violations)
