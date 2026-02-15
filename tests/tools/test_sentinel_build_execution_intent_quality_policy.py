from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict


def _load_module() -> Any:
    root = Path(__file__).resolve().parents[2]
    mod_path = root / "tools" / "sentinel_build_execution_intent.py"
    spec = importlib.util.spec_from_file_location("sentinel_build_execution_intent", mod_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _policy_with_mode(mode: str) -> Dict[str, Any]:
    return {
        "schema": "sentinel_exec_trigger_policy.v1",
        "policy_id": "EXEC_TRIGGER_V1",
        "version": "1.0",
        "rules": [],
        "default": {"triggered": False, "reason_code": "NO_ACTION_CONDITIONS_NOT_MET"},
        "quality_policy": {
            "mode": mode,
            "soft_gate": {
                "warn": {"size_multiplier": 0.5, "allow_new_entries": True, "reduce_only": False},
                "error": {"size_multiplier": 0.2, "allow_new_entries": False, "reduce_only": True},
            },
            "hard_gate": {"deny_on": {"evidence_not_ok": True, "severity_error": True}},
        },
    }


def _base_summary(quality: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema": "sentinel_summary.v0",
        "ts": "20260215T120000Z",
        "items": [
            {
                "symbol": "BTCUSDT",
                "timeframe": "15m",
                "oi_delta_pct": 0.0,
                "final": {
                    "final_score": 80,
                    "final_direction": "long",
                    "final_risk_level": "medium",
                    "final_confidence": 0.8,
                    "final_snapshot_path": "/tmp/metaos_snapshots/BTCUSDT_15m/snapshot_20260215T120000Z.json",
                },
                "quality": quality,
            }
        ],
    }


def _run_main(mod: Any, monkeypatch, summary_file: Path, policy_file: Path, outbox: Path) -> Dict[str, Any]:
    argv = [
        "sentinel_build_execution_intent.py",
        "--summary-file",
        str(summary_file),
        "--outbox",
        str(outbox),
        "--policy-file",
        str(policy_file),
        "--execution-mode",
        "live",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    rc = mod.main()
    assert rc == 0
    out = outbox / "intent_20260215T120000Z.json"
    return json.loads(out.read_text(encoding="utf-8"))


def test_quality_policy_observer_keeps_trigger_behavior(tmp_path: Path, monkeypatch) -> None:
    mod = _load_module()
    policy_file = tmp_path / "policy.yaml"
    summary_file = tmp_path / "summary.json"
    outbox = tmp_path / "outbox"
    _write_json(summary_file, _base_summary({"evidence_ok": True, "severity_max": "warn"}))
    policy_file.write_text(json.dumps(_policy_with_mode("observer")), encoding="utf-8")

    intent = _run_main(mod, monkeypatch, summary_file, policy_file, outbox)
    item = intent["intent"]["items"][0]
    assert item["triggered"] is True
    assert item["quality"]["mode"] == "observer"
    assert item["quality"]["effects"]["size_multiplier"] == 1.0
    assert item["quality"]["effects"]["deny"] is False


def test_quality_policy_soft_gate_adjusts_size(tmp_path: Path, monkeypatch) -> None:
    mod = _load_module()
    policy_file = tmp_path / "policy.yaml"
    summary_file = tmp_path / "summary.json"
    outbox = tmp_path / "outbox"
    _write_json(summary_file, _base_summary({"evidence_ok": True, "severity_max": "warn"}))
    policy_file.write_text(json.dumps(_policy_with_mode("soft_gate")), encoding="utf-8")

    intent = _run_main(mod, monkeypatch, summary_file, policy_file, outbox)
    item = intent["intent"]["items"][0]
    assert item["triggered"] is True
    assert item["quality"]["mode"] == "soft_gate"
    assert item["quality"]["effects"]["size_multiplier"] == 0.5
    assert item["quality"]["effects"]["reduce_only"] is False


def test_quality_policy_hard_gate_denies(tmp_path: Path, monkeypatch) -> None:
    mod = _load_module()
    policy_file = tmp_path / "policy.yaml"
    summary_file = tmp_path / "summary.json"
    outbox = tmp_path / "outbox"
    _write_json(summary_file, _base_summary({"evidence_ok": False, "severity_max": "error"}))
    policy_file.write_text(json.dumps(_policy_with_mode("hard_gate")), encoding="utf-8")

    intent = _run_main(mod, monkeypatch, summary_file, policy_file, outbox)
    item = intent["intent"]["items"][0]
    assert item["triggered"] is False
    assert item["reason_code"] == "QUALITY_HARD_GATE_DENY"
    assert item["quality"]["mode"] == "hard_gate"
    assert item["quality"]["effects"]["deny"] is True
    assert item["quality"]["effects"]["allow_new_entries"] is False
