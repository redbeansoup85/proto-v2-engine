from __future__ import annotations

import json
from pathlib import Path

from tools.gates.gate_authority_decision import validate_decision, validate_or_record


def _decision() -> dict:
    return {
        "run_id": "RUN-DECISION-001",
        "ts_utc": "2026-02-19T00:00:00Z",
        "symbol": "SOLUSDT",
        "timeframe": "15m",
        "decision": "NO_TRADE",
        "reason": "authority_stub_no_trade",
        "evidence": {
            "authority": "authority_stub",
            "provider_schema_id": "sentinel_raw_snapshot.v1",
        },
    }


def test_valid_no_trade_passes(tmp_path: Path) -> None:
    d = _decision()
    assert validate_decision(d) == []
    assert validate_or_record(d, exceptions_dir=tmp_path / "Exceptions")


def test_rejects_missing_required_key(tmp_path: Path) -> None:
    d = _decision()
    d.pop("reason")
    assert not validate_or_record(d, exceptions_dir=tmp_path / "Exceptions")
    violations = validate_decision(d)
    assert any(v["reason"] == "missing_required_key" and v["path"] == "reason" for v in violations)


def test_rejects_invalid_enum() -> None:
    d = _decision()
    d["decision"] = "HOLD"
    violations = validate_decision(d)
    assert any(v["reason"] == "invalid_decision_enum" for v in violations)


def test_rejects_forbidden_field() -> None:
    d = _decision()
    d["qty"] = 5
    violations = validate_decision(d)
    assert any(v["reason"] == "forbidden_field_name" and v["path"] == "qty" for v in violations)


def test_rejects_missing_evidence_provider_schema_id(tmp_path: Path) -> None:
    d = _decision()
    d["evidence"] = {"authority": "authority_stub"}
    assert not validate_or_record(d, exceptions_dir=tmp_path / "Exceptions")
    out = tmp_path / "Exceptions" / "RUN-DECISION-001.jsonl"
    assert out.exists()
    row = json.loads(out.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["layer"] == "authority_decision_gate"
    assert any(v["reason"] == "missing_evidence_provider_schema_id" for v in row["violations"])
