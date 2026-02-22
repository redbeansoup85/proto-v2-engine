from __future__ import annotations

from types import SimpleNamespace

import infra.api.routes.executor as executor_route
import pytest
from fastapi import HTTPException


def _valid_intent() -> dict:
    return {
        "schema": "execution_intent.v1",
        "domain": "SENTINEL_EXEC",
        "event_id": "EVT-LIVE-KILL-001",
        "intent": {
            "items": [
                {
                    "final_confidence": 0.8,
                    "quality": {"effects": {"size_multiplier": 1.0}},
                }
            ]
        },
        "risk_regime_input": {
            "gate_hits": {"vix": False, "dxy": False, "real10y": False, "btcvol": False},
            "missing": [],
            "hard_kill": False,
        },
    }


class _StubRegime:
    def __init__(self, current: str, target: str | None = None):
        self._current = current
        self._target = target or current

    def update(self, **_kwargs):
        return SimpleNamespace(
            as_dict=lambda: {
                "current_regime": self._current,
                "target_regime": self._target,
                "reasons": [],
                "missing": [],
                "entered_at": 0,
                "normalized_since": None,
                "cooldown_remaining_ms": 0,
            }
        )


@pytest.fixture(autouse=True)
def _reset_kill_switch(monkeypatch):
    monkeypatch.setattr(executor_route, "_read_kill_file", lambda: False)
    monkeypatch.setattr(executor_route, "_KILL_SWITCH", False)


def test_live_kill_switch_blocks_when_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("LIVE_TRADING_ENABLED", raising=False)
    out = executor_route.execute_market({})
    assert out == {"status": "blocked_by_env", "reason": "LIVE_TRADING_DISABLED"}


def test_live_kill_switch_blocks_when_env_false(monkeypatch) -> None:
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "false")
    out = executor_route.execute_market(_valid_intent())
    assert out == {"status": "blocked_by_env", "reason": "LIVE_TRADING_DISABLED"}


def test_live_kill_switch_allows_path_when_env_true(monkeypatch) -> None:
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    monkeypatch.setattr(executor_route, "_recent_event_id_exists", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(executor_route, "get_regime_warden", lambda: _StubRegime("NORMAL"))

    called = {"n": 0}

    def _fake_run(*_args, **_kwargs):
        called["n"] += 1
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(executor_route.subprocess, "run", _fake_run)
    out = executor_route.execute_market(_valid_intent())
    assert out["status"] == "ok"
    assert called["n"] == 1

def test_live_gate_soft_mode_returns_blocked_response(monkeypatch) -> None:
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    monkeypatch.setenv("LIVE_GATE_ENFORCE", "1")
    monkeypatch.setenv("LIVE_GATE_MODE", "soft")
    monkeypatch.setattr(executor_route, "get_regime_warden", lambda: _StubRegime("NORMAL"))

    # ensure idempotency check doesn't block
    monkeypatch.setattr(executor_route, "_recent_event_id_exists", lambda *_args, **_kwargs: False)

    # force gate to block
    monkeypatch.setattr(executor_route, "validate_or_record", lambda *_args, **_kwargs: False)

    out = executor_route.execute_market(_valid_intent())
    assert out["status"] == "blocked_by_gate"
    assert "live_gate_blocked:" in out["reason"]


def test_regime_shock_blocks_new_entries(monkeypatch) -> None:
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    monkeypatch.setattr(executor_route, "get_regime_warden", lambda: _StubRegime("SHOCK"))
    monkeypatch.setattr(executor_route, "_recent_event_id_exists", lambda *_args, **_kwargs: False)
    with pytest.raises(HTTPException) as exc:
        executor_route.execute_market(_valid_intent())
    assert "risk_regime_shock_new_entries_blocked" in str(exc.value.detail)


def test_regime_black_swan_turns_on_kill_switch(monkeypatch) -> None:
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    monkeypatch.setattr(executor_route, "get_regime_warden", lambda: _StubRegime("BLACK_SWAN"))
    monkeypatch.setattr(executor_route, "_recent_event_id_exists", lambda *_args, **_kwargs: False)

    wrote = {"v": None}
    monkeypatch.setattr(executor_route, "_write_kill_file", lambda val: wrote.update(v=val))
    with pytest.raises(HTTPException) as exc:
        executor_route.execute_market(_valid_intent())
    assert "risk_regime_black_swan_kill_switch" in str(exc.value.detail)
    assert wrote["v"] is True


def test_regime_warning_applies_size_scale(monkeypatch) -> None:
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    monkeypatch.setattr(executor_route, "get_regime_warden", lambda: _StubRegime("WARNING"))
    monkeypatch.setattr(executor_route, "_recent_event_id_exists", lambda *_args, **_kwargs: False)

    def _fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(executor_route.subprocess, "run", _fake_run)
    intent = _valid_intent()
    executor_route.execute_market(intent)
    item = intent["intent"]["items"][0]
    assert item["final_confidence"] == 0.4
    assert item["quality"]["effects"]["size_multiplier"] == 0.5
