import os
import pytest
from core.adapters.mock_adapter import MockAdapter, AdapterError

def test_mock_adapter_ok(monkeypatch):
    monkeypatch.setenv("MOCK_ADAPTER_MODE", "ok")
    out = MockAdapter().call({"ping": 1})
    assert out["ok"] is True
    assert out["echo"]["ping"] == 1

def test_mock_adapter_mismatch(monkeypatch):
    monkeypatch.setenv("MOCK_ADAPTER_MODE", "mismatch")
    out = MockAdapter().call({"ping": 1})
    assert "unexpected_field" in out

def test_mock_adapter_error(monkeypatch):
    monkeypatch.setenv("MOCK_ADAPTER_MODE", "error")
    with pytest.raises(AdapterError):
        MockAdapter().call({"ping": 1})
