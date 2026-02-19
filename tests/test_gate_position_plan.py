from __future__ import annotations

from tools.gates.gate_position_plan import validate_plan, validate_or_record


def _plan() -> dict:
    return {
        "run_id": "RUN-PLAN-001",
        "ts_utc": "2026-02-19T00:00:00Z",
        "symbol": "SOLUSDT",
        "timeframe": "15m",
        "direction": "NO_TRADE",
        "size": 0.0,
        "mode": "NO_EXEC",
        "risk": {
            "max_risk_pct": 0.0,
            "sizing_method": "stub_no_exec",
        },
        "evidence": {
            "decision_reason": "authority_stub_no_trade",
        },
    }


def test_valid_no_exec_plan_passes(tmp_path) -> None:
    plan = _plan()
    assert validate_plan(plan) == []
    assert validate_or_record(plan, exceptions_dir=tmp_path / "Exceptions")


def test_rejects_negative_size() -> None:
    plan = _plan()
    plan["size"] = -1.0
    violations = validate_plan(plan)
    assert any(v["reason"] == "size_negative" for v in violations)


def test_rejects_invalid_mode() -> None:
    plan = _plan()
    plan["mode"] = "EXECUTE"
    violations = validate_plan(plan)
    assert any(v["reason"] == "invalid_mode_enum" for v in violations)


def test_rejects_missing_risk_key() -> None:
    plan = _plan()
    del plan["risk"]["sizing_method"]
    violations = validate_plan(plan)
    assert any(v["reason"] == "missing_risk_key" and v["path"] == "risk.sizing_method" for v in violations)


def test_rejects_forbidden_field() -> None:
    plan = _plan()
    plan["qty"] = 5
    violations = validate_plan(plan)
    assert any(v["reason"] == "forbidden_field_name" and v["path"] == "qty" for v in violations)
