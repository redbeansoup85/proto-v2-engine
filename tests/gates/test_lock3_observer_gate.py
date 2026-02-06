from __future__ import annotations

import json
from pathlib import Path

from tools.audit.observer_hasher import hash_event
from tools.gates import lock3_observer_gate


def _event(
    *,
    event_id: str,
    judgment_id: str,
    approval_record_id: str,
    execution_run_id: str,
    status: str,
    metrics: dict,
    prev_hash: str,
) -> dict:
    obj = {
        "schema_version": "lock3/observer_event@1.0",
        "event_id": event_id,
        "ts": "2026-02-05T00:00:00Z",
        "judgment_id": judgment_id,
        "approval_record_id": approval_record_id,
        "execution_run_id": execution_run_id,
        "status": status,
        "metrics": metrics,
        "prev_hash": prev_hash,
    }
    obj["hash"] = hash_event(prev_hash, obj)
    return obj


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    lines = [json.dumps(r, ensure_ascii=False) for r in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_pass_two_events(tmp_path: Path) -> None:
    path = tmp_path / "lock3.jsonl"
    genesis = "0" * 64
    e1 = _event(
        event_id="EVT-0001",
        judgment_id="J-1",
        approval_record_id="A-1",
        execution_run_id="R-1",
        status="started",
        metrics={},
        prev_hash=genesis,
    )
    e2 = _event(
        event_id="EVT-0002",
        judgment_id="J-1",
        approval_record_id="A-1",
        execution_run_id="R-1",
        status="ok",
        metrics={"latency_ms": 12},
        prev_hash=e1["hash"],
    )
    _write_jsonl(path, [e1, e2])

    code, findings = lock3_observer_gate.run_observer_gate(path=path)
    assert code == 0
    assert findings == []


def test_fail_chain_broken(tmp_path: Path) -> None:
    path = tmp_path / "lock3.jsonl"
    genesis = "0" * 64
    e1 = _event(
        event_id="EVT-0001",
        judgment_id="J-1",
        approval_record_id="A-1",
        execution_run_id="R-1",
        status="started",
        metrics={},
        prev_hash=genesis,
    )
    e2 = _event(
        event_id="EVT-0002",
        judgment_id="J-1",
        approval_record_id="A-1",
        execution_run_id="R-1",
        status="ok",
        metrics={},
        prev_hash="1" * 64,
    )
    _write_jsonl(path, [e1, e2])

    code, findings = lock3_observer_gate.run_observer_gate(path=path)
    assert code == 1
    assert any(f.rule_id == "LOCK3_CHAIN_BROKEN" for f in findings)


def test_fail_link_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "lock3.jsonl"
    genesis = "0" * 64
    e1 = _event(
        event_id="EVT-0001",
        judgment_id="J-1",
        approval_record_id="A-1",
        execution_run_id="R-1",
        status="started",
        metrics={},
        prev_hash=genesis,
    )
    e2 = _event(
        event_id="EVT-0002",
        judgment_id="J-2",
        approval_record_id="A-1",
        execution_run_id="R-1",
        status="ok",
        metrics={},
        prev_hash=e1["hash"],
    )
    _write_jsonl(path, [e1, e2])

    code, findings = lock3_observer_gate.run_observer_gate(path=path)
    assert code == 1
    assert any(f.rule_id == "LOCK3_LINK_MISMATCH" for f in findings)


def test_fail_schema_extra_metric(tmp_path: Path) -> None:
    path = tmp_path / "lock3.jsonl"
    genesis = "0" * 64
    e1 = _event(
        event_id="EVT-0001",
        judgment_id="J-1",
        approval_record_id="A-1",
        execution_run_id="R-1",
        status="started",
        metrics={"extra": "nope"},
        prev_hash=genesis,
    )
    _write_jsonl(path, [e1])

    code, findings = lock3_observer_gate.run_observer_gate(path=path)
    assert code == 1
    assert any(f.rule_id == "LOCK3_SCHEMA_INVALID" for f in findings)


def test_fail_parse_error(tmp_path: Path) -> None:
    path = tmp_path / "lock3.jsonl"
    path.write_text("{bad json}\n", encoding="utf-8")

    code, findings = lock3_observer_gate.run_observer_gate(path=path)
    assert code == 1
    assert any(f.rule_id == "LOCK3_PARSE_ERROR" for f in findings)
