import os
import pytest
from core.adapters.mock_adapter import MockAdapter, AdapterError

def test_mock_adapter_ok(monkeypatch):
    monkeypatch.setenv("MOCK_ADAPTER_MODE", "ok")
    out = MockAdapter().call({"ping": 1})
    assert out["ok"] is True
    assert out["engine_output"]["decision"]["status"] == "ALLOW"
    assert out["engine_output"]["meta"]["adapter"]["name"] == "mock"
    assert len(out["engine_output"]["meta"]["request_hash"]) == 64

def test_mock_adapter_mismatch(monkeypatch):
    monkeypatch.setenv("MOCK_ADAPTER_MODE", "mismatch")
    out = MockAdapter().call({"ping": 1})
    assert "unexpected_field" in out

def test_mock_adapter_ambiguous(monkeypatch):
    monkeypatch.setenv("MOCK_ADAPTER_MODE", "ambiguous")
    out = MockAdapter().call({"ping": 1})
    assert out["ok"] is False
    assert out["engine_output"]["decision"]["status"] == "AMBIGUOUS"

def test_mock_adapter_error(monkeypatch):
    monkeypatch.setenv("MOCK_ADAPTER_MODE", "error")
    with pytest.raises(AdapterError):
        MockAdapter().call({"ping": 1})
