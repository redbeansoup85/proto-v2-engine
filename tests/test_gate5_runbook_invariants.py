from __future__ import annotations

import json
from typing import Any, Dict

from infra.api.audit_sink import emit_audit_event


def _base_event(**overrides: Any) -> Dict[str, Any]:
    event = {
        # Minimal required audit fields from Gate 5 runbook
        "event_id": "evt-1",
        "ts_iso": "2026-01-18T00:00:00Z",
        "actor": "system",
        "action": "integration_attempt",
        "outcome": "deny",
        "approval_id": "apr-1",
        "correlation_id": "corr-1",
        "refs": ["ui://gate5/runbook"],
    }
    event.update(overrides)
    return event


def _assert_min_fields(e: Dict[str, Any]) -> None:
    for k in ("event_id", "ts_iso", "actor", "action", "outcome", "refs"):
        assert k in e
    # at least one of these identifiers must exist for traceability
    assert ("approval_id" in e) or ("execution_id" in e) or ("correlation_id" in e)


def test_gate5_s1_adapter_timeout_emits_audit(capfd):
    e = _base_event(event="INTEGRATION_FAILED_TIMEOUT", action="adapter_call", outcome="deny")
    _assert_min_fields(e)
    emit_audit_event(e)

    out, err = capfd.readouterr()
    assert out.strip()  # JSONL line
    payload = json.loads(out.strip().splitlines()[-1])
    assert payload["event"] == "INTEGRATION_FAILED_TIMEOUT"
    assert payload["outcome"] == "deny"
    assert "recorded_at" in payload


def test_gate5_s2_contract_violation_emits_audit(capfd):
    e = _base_event(event="ADAPTER_CONTRACT_VIOLATION", action="validate_adapter_payload", outcome="deny")
    _assert_min_fields(e)
    emit_audit_event(e)

    out, _ = capfd.readouterr()
    payload = json.loads(out.strip().splitlines()[-1])
    assert payload["event"] == "ADAPTER_CONTRACT_VIOLATION"
    assert payload["outcome"] == "deny"


def test_gate5_s3_ambiguous_result_emits_audit(capfd):
    e = _base_event(event="INTEGRATION_AMBIGUOUS_RESULT", action="integration_result", outcome="deny")
    _assert_min_fields(e)
    emit_audit_event(e)

    out, _ = capfd.readouterr()
    payload = json.loads(out.strip().splitlines()[-1])
    assert payload["event"] == "INTEGRATION_AMBIGUOUS_RESULT"
    assert payload["outcome"] == "deny"


def test_gate5_s4_replay_blocked_emits_audit(capfd):
    e = _base_event(event="INTEGRATION_REPLAY_BLOCKED", action="idempotency_check", outcome="deny")
    _assert_min_fields(e)
    emit_audit_event(e)

    out, _ = capfd.readouterr()
    payload = json.loads(out.strip().splitlines()[-1])
    assert payload["event"] == "INTEGRATION_REPLAY_BLOCKED"
    assert payload["outcome"] == "deny"


def test_gate5_s5_audit_sink_never_raises(monkeypatch, capfd):
    # Simulate stdout failure: emit_audit_event must not raise; must write fallback to stderr.
    def _boom_write(*args, **kwargs):
        raise RuntimeError("stdout broken")

    monkeypatch.setattr("sys.stdout.write", _boom_write)

    e = _base_event(event="AUDIT_SINK_UNAVAILABLE", action="emit_audit_event", outcome="deny")
    _assert_min_fields(e)

    emit_audit_event(e)  # must not raise

    out, err = capfd.readouterr()
    assert out == ""
    assert err.strip()
    payload = json.loads(err.strip().splitlines()[-1])
    assert payload["event"] == "audit_error"
    assert payload["outcome"] == "deny"
    assert "recorded_at" in payload


def test_gate5_s6_missing_approval_denies(capfd):
    e = _base_event(
        event="STATE_TRANSITION_MISSING_APPROVAL",
        action="state_transition_request",
        outcome="deny",
    )
    # Remove approval_id to simulate missing approval; correlation_id still provides traceability
    e.pop("approval_id", None)
    _assert_min_fields(e)

    emit_audit_event(e)
    out, _ = capfd.readouterr()
    payload = json.loads(out.strip().splitlines()[-1])
    assert payload["event"] == "STATE_TRANSITION_MISSING_APPROVAL"
    assert payload["outcome"] == "deny"
