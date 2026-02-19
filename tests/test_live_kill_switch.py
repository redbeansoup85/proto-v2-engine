from __future__ import annotations

from types import SimpleNamespace

import infra.api.routes.executor as executor_route


def _valid_intent() -> dict:
    return {
        "schema": "execution_intent.v1",
        "domain": "SENTINEL_EXEC",
        "event_id": "EVT-LIVE-KILL-001",
    }


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

    # ensure idempotency check doesn't block
    monkeypatch.setattr(executor_route, "_recent_event_id_exists", lambda *_args, **_kwargs: False)

    # force gate to block
    monkeypatch.setattr(executor_route, "validate_or_record", lambda *_args, **_kwargs: False)

    out = executor_route.execute_market(_valid_intent())
    assert out["status"] == "blocked_by_gate"
    assert "live_gate_blocked:" in out["reason"]

