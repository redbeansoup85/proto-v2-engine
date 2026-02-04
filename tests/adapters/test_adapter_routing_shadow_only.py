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


def test_run_adapter_defaults_to_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SHADOW_ONLY", raising=False)
    monkeypatch.setenv("MOCK_ADAPTER_MODE", "ok")
    result = run_adapter(adapter_name="mock", request=_VALID_REQUEST)
    assert isinstance(result, dict)
    assert result["ok"] is True


def test_run_adapter_false_routes_to_enforced_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHADOW_ONLY", "false")
    monkeypatch.setenv("MOCK_ADAPTER_MODE", "ok")
    with pytest.raises(ShadowAdapterError):
        run_adapter(adapter_name="mock", request=_VALID_REQUEST)
