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
    "event": {"type": "TEST_EVENT", "payload": {}},
    "signals": [],
    "proposed_decision": None,
    "human_decision": None,
}

def test_run_adapter_shadow_default(monkeypatch):
    monkeypatch.setenv("SHADOW_ONLY", "true")
    result = run_adapter(adapter_name="mock", request=_VALID_REQUEST)
    assert isinstance(result, dict)
    assert result["ok"] is True

def test_run_adapter_enforced_fail_closed(monkeypatch):
    monkeypatch.setenv("SHADOW_ONLY", "false")
    with pytest.raises(ShadowAdapterError):
        run_adapter(adapter_name="mock", request=_VALID_REQUEST)
