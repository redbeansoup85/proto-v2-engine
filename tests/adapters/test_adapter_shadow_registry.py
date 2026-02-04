from __future__ import annotations

import pytest

from core.execution.executor import ShadowAdapterError, run_adapter


_VALID_REQUEST = {
    "meta": {
        "org_id": "org-1",
        "site_id": "site-1",
        "source": "unit",
        "ts_start_iso": "2026-02-04T00:00:00Z",
        "ts_end_iso": "2026-02-04T00:01:00Z",
    },
    "event": {
        "type": "TEST_EVENT",
        "payload": {},
    },
    "signals": [],
    "proposed_decision": None,
    "human_decision": None,
}


def test_adapter_selection_requires_explicit_name(monkeypatch):
    monkeypatch.setenv("MOCK_ADAPTER_MODE", "ok")
    with pytest.raises(ShadowAdapterError, match="adapter_name is required"):
        run_adapter(adapter_name=None, request=_VALID_REQUEST)


def test_unknown_adapter_fails_closed(monkeypatch):
    monkeypatch.setenv("MOCK_ADAPTER_MODE", "ok")
    with pytest.raises(ShadowAdapterError, match="unknown adapter"):
        run_adapter(adapter_name="unknown", request=_VALID_REQUEST)


def test_mock_shadow_path_contract_compliant(monkeypatch):
    monkeypatch.setenv("MOCK_ADAPTER_MODE", "ok")
    result = run_adapter(adapter_name="mock", request=_VALID_REQUEST)
    assert result["ok"] is True
    assert result["engine_output"]["decision"]["status"] == "ALLOW"


def test_request_contract_mismatch_fails_closed(monkeypatch):
    monkeypatch.setenv("MOCK_ADAPTER_MODE", "ok")
    bad_request = {
        "meta": {
            "org_id": "org-1",
            "site_id": "site-1",
            "source": "unit",
            "ts_start_iso": "2026-02-04T00:00:00Z",
            # ts_end_iso missing
        },
        "event": {"type": "TEST_EVENT", "payload": {}},
    }
    with pytest.raises(ShadowAdapterError, match="missing required key"):
        run_adapter(adapter_name="mock", request=bad_request)


def test_response_contract_mismatch_fails_closed(monkeypatch):
    monkeypatch.setenv("MOCK_ADAPTER_MODE", "mismatch")
    with pytest.raises(ShadowAdapterError, match="missing required key"):
        run_adapter(adapter_name="mock", request=_VALID_REQUEST)


def test_timeout_and_ambiguous_are_explicit(monkeypatch):
    monkeypatch.setenv("MOCK_ADAPTER_MODE", "timeout")
    monkeypatch.setenv("MOCK_ADAPTER_TIMEOUT_MS", "1")
    with pytest.raises(ShadowAdapterError, match="adapter call failed: ADAPTER_TIMEOUT"):
        run_adapter(adapter_name="mock", request=_VALID_REQUEST)

    monkeypatch.setenv("MOCK_ADAPTER_MODE", "ambiguous")
    result = run_adapter(adapter_name="mock", request=_VALID_REQUEST)
    assert result["ok"] is False
    assert result["engine_output"]["decision"]["status"] == "AMBIGUOUS"
