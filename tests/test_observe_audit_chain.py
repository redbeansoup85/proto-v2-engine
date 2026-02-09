from __future__ import annotations

import json
from dataclasses import dataclass
import importlib
from pathlib import Path

import pytest

from core.contracts.orchestrator import DeliveryPlan
from core.contracts.policy import DecisionMode, Severity
from core.contracts.rationale_codes import RationaleCode
from core.contracts.scene import SceneContext, SceneRef, SceneStatus
from infra.api.schemas import DecisionIn

observe_mod = importlib.import_module("tools.observe.observe_event")


def _canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class _DecisionStub:
    mode: DecisionMode
    severity: Severity
    rationale_codes: tuple[RationaleCode, ...]


@dataclass(frozen=True)
class _RoutingStub:
    delivery_plan: DeliveryPlan
    auto_action: bool
    targets: tuple[str, ...]
    metadata: dict


class _Policy:
    def decide(self, channel: str, signals: dict):
        return _DecisionStub(
            mode=DecisionMode.observe_more,
            severity=Severity.low,
            rationale_codes=(RationaleCode.NO_ACTION_BY_POLICY,),
        )


class _Orch:
    def route(self, channel, severity):
        return _RoutingStub(
            delivery_plan=DeliveryPlan.ALERT_ONLY,
            auto_action=False,
            targets=("vault",),
            metadata={},
        ), (), ()


class _L2:
    def append_decision_snapshot(self, snapshot: dict):
        return "snap_1"


class _Scenes:
    def __init__(self):
        self._active = None

    def get_active_by_context(self, context_key: str):
        return self._active

    def open_new_scene(self, context: SceneContext, ts_start: str):
        self._active = SceneRef(
            scene_id="scene_1",
            status=SceneStatus.ACTIVE,
            context=context,
            ts_start=ts_start,
        )
        return self._active

    def upsert_active(self, active):
        self._active = active

    def clear_active(self, context_key: str):
        self._active = None


def _valid_event() -> dict:
    return {
        "event_id": "obs_test_1",
        "ts": "2026-02-09T00:00:00Z",
        "schema_id": "kernel.observe_event.v1",
        "kind": "decision_ingest",
        "meta": {"org_id": "org1", "site_id": "site1", "channel": "childcare"},
        "preview": {"payload_keys": ["meta", "signals"], "signals_keys": ["x"], "signals_count": 1},
    }


def test_observe_event_appends_logs_and_chain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    observer_path = tmp_path / "events.jsonl"
    chain_path = tmp_path / "chain.jsonl"
    monkeypatch.setattr(observe_mod, "DEFAULT_OBSERVER_PATH", observer_path)
    monkeypatch.setattr(observe_mod, "DEFAULT_CHAIN_PATH", chain_path)

    observe_mod.observe_event(_valid_event(), channel="childcare", source_path="test", request_id=None)
    ev2 = _valid_event()
    ev2["event_id"] = "obs_test_2"
    observe_mod.observe_event(ev2, channel="childcare", source_path="test", request_id="req-1")

    chain_rows = [json.loads(x) for x in chain_path.read_text(encoding="utf-8").splitlines()]
    assert len(chain_rows) == 2
    assert chain_rows[0]["prev_hash"] == "0" * 64
    assert chain_rows[1]["prev_hash"] == chain_rows[0]["hash"]
    calc0 = observe_mod._sha256_hex(_canonical_json({k: v for k, v in chain_rows[0].items() if k != "hash"}).encode("utf-8"))
    calc1 = observe_mod._sha256_hex(_canonical_json({k: v for k, v in chain_rows[1].items() if k != "hash"}).encode("utf-8"))
    assert chain_rows[0]["hash"] == calc0
    assert chain_rows[1]["hash"] == calc1


def test_fail_closed_on_forbidden_key_no_partial_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    observer_path = tmp_path / "events.jsonl"
    chain_path = tmp_path / "chain.jsonl"
    monkeypatch.setattr(observe_mod, "DEFAULT_OBSERVER_PATH", observer_path)
    monkeypatch.setattr(observe_mod, "DEFAULT_CHAIN_PATH", chain_path)

    bad = _valid_event()
    bad["meta"]["token"] = "forbidden"
    with pytest.raises(RuntimeError):
        observe_mod.observe_event(bad, channel="childcare", source_path="test", request_id=None)

    assert not observer_path.exists() or observer_path.read_text(encoding="utf-8") == ""
    assert not chain_path.exists() or chain_path.read_text(encoding="utf-8") == ""


def test_decision_ingest_calls_observe_event(monkeypatch: pytest.MonkeyPatch) -> None:
    import infra.api.deps as deps

    # decision.py imports these names at module import time.
    monkeypatch.setattr(deps, "get_policy", lambda: None, raising=False)
    monkeypatch.setattr(deps, "get_orchestrator", lambda: None, raising=False)
    monkeypatch.setattr(deps, "get_l2", lambda: None, raising=False)
    monkeypatch.setattr(deps, "get_scene_repo", lambda: None, raising=False)
    monkeypatch.setattr(deps, "get_scene_state_map", lambda: {}, raising=False)
    monkeypatch.setattr(deps, "get_l3_learning", lambda: None, raising=False)
    decision_mod = importlib.import_module("infra.api.routes.decision")

    calls: list[dict] = []

    def _stub_observe_event(event, *, channel, source_path, request_id):
        calls.append(
            {
                "event": event,
                "channel": channel,
                "source_path": source_path,
                "request_id": request_id,
            }
        )
        return {"ok": True}

    monkeypatch.setattr(decision_mod, "observe_event", _stub_observe_event, raising=True)
    payload = DecisionIn.model_validate(
        {
            "meta": {
                "org_id": "org1",
                "site_id": "site1",
                "channel": "childcare",
                "window": {"start_ts": "2026-02-09T00:00:00Z", "end_ts": "2026-02-09T00:01:00Z"},
            },
            "signals": {"force_close": False, "risk": "low"},
        }
    )

    out = decision_mod.ingest(
        payload=payload,
        policy=_Policy(),
        orch=_Orch(),
        l2=_L2(),
        scenes=_Scenes(),
        scene_state_map={},
    )
    assert out.meta.org_id == "org1"
    assert len(calls) == 1
    assert calls[0]["event"]["kind"] == "decision_ingest"
