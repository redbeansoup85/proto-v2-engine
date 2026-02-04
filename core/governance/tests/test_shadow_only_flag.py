import pytest

from core.execution.executor import is_shadow_only


def test_shadow_only_default_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SHADOW_ONLY", raising=False)
    assert is_shadow_only() is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "n"])
def test_shadow_only_false_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("SHADOW_ONLY", value)
    assert is_shadow_only() is False


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", "y"])
def test_shadow_only_true_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("SHADOW_ONLY", value)
    assert is_shadow_only() is True


def test_shadow_only_invalid_fail_closed_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHADOW_ONLY", "???")
    assert is_shadow_only() is True
