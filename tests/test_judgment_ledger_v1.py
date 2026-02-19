from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from tools.judgment.judgment_ledger import append_judgment
from tools.gates.lock3_observer_gate import run_observer_gate


def test_append_judgment_writes_jsonl(tmp_path: Path) -> None:
    ledger = tmp_path / "judgment.v1.jsonl"

    j = append_judgment(
        verdict="INFO",
        actor="test",
        reason="hello",
        domain="SENTINEL_EXEC",
        symbol="SOLUSDT",
        side="SHORT",
        policy_sha256="deadbeef",
        refs={"execution_intent_hash": "abc123"},
        ledger_path=ledger,
    )

    assert j["schema"] == "judgment.v1"
    assert j["actor"] == "test"
    assert j["verdict"] == "INFO"

    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["schema"] == "judgment.v1"
    assert parsed["refs"]["execution_intent_hash"] == "abc123"


def test_judgment_schema_selftest(tmp_path: Path) -> None:
    schema_path = Path("schemas/judgment.v1.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    ledger = tmp_path / "judgment.v1.jsonl"
    row = append_judgment(verdict="WARN", actor="schema-test", ledger_path=ledger)
    errs = list(validator.iter_errors(row))
    assert errs == []


def test_sample_append_and_chain_connectivity(tmp_path: Path) -> None:
    ledger = tmp_path / "judgment.v1.jsonl"
    j1 = append_judgment(verdict="INFO", actor="chain-test", ledger_path=ledger)
    j2 = append_judgment(
        verdict="INFO",
        actor="chain-test",
        refs={"decision_id": j1["judgment_id"]},
        ledger_path=ledger,
    )

    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    p1 = json.loads(lines[0])
    p2 = json.loads(lines[1])
    assert p1["judgment_id"] == j1["judgment_id"]
    assert p2["judgment_id"] == j2["judgment_id"]
    assert p2["refs"]["decision_id"] == p1["judgment_id"]


def test_replay_gate_impact_none() -> None:
    code, findings = run_observer_gate(path=Path("tests/fixtures/observer/valid_observer.jsonl"))
    assert code == 0
    assert findings == []
