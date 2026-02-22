from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from infra.api.app import app
import infra.api.routes.executor as executor_route

KILL_FILE = Path("var/metaos/state/executor_kill_switch.txt")


def _reset_kill_switch_state() -> None:
    executor_route._KILL_SWITCH = False
    if KILL_FILE.exists():
        KILL_FILE.unlink()


@pytest.fixture(autouse=True)
def _cleanup_kill_state():
    _reset_kill_switch_state()
    yield
    _reset_kill_switch_state()


def test_kill_switch_blocks_execution(monkeypatch) -> None:
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    _reset_kill_switch_state()

    with TestClient(app) as client:
        kill_res = client.post("/api/executor/kill", json={})
        assert kill_res.status_code == 200

        res = client.post("/execute_market", json={})
        assert res.status_code == 423
        assert "kill_switch_file=1" in str(res.json().get("detail"))


def test_live_disabled_blocks_execution(monkeypatch) -> None:
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "false")
    _reset_kill_switch_state()

    with TestClient(app) as client:
        res = client.post("/execute_market", json={})
        assert res.status_code == 423
        assert "live_trading_disabled" in str(res.json().get("detail"))


def test_empty_intent_returns_400(monkeypatch) -> None:
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    _reset_kill_switch_state()

    with TestClient(app) as client:
        res = client.post("/execute_market", json={})
        assert res.status_code == 400


def test_invalid_schema_returns_400(monkeypatch) -> None:
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    _reset_kill_switch_state()

    with TestClient(app) as client:
        res = client.post("/execute_market", json={"schema": "wrong"})
        assert res.status_code == 400
