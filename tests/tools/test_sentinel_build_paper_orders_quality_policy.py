from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


TOOL = Path("tools/sentinel_build_paper_orders.py")


def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _policy() -> Dict[str, Any]:
    return {
        "schema": "sentinel_paper_orders_policy.v1",
        "policy_id": "PAPER_ORDERS_V1",
        "version": "1.0",
        "defaults": {
            "venue": "bybit",
            "product": "perp",
            "leverage": 2,
            "sizing": {"equity_pct": 0.02},
            "sl": {"atr_mult": 1.5},
            "tp": {"r_multiple": 2.0},
        },
        "rules": [
            {
                "id": "PAPER_ONLY",
                "priority": 10,
                "when": {
                    "execution_mode_in": ["paper"],
                    "triggered_is": True,
                    "direction_in": ["long", "short"],
                    "risk_level_in": ["low", "medium"],
                    "confidence_gte": 0.55,
                    "score_gte": 60,
                    "oi_delta_pct_gt": -1.0,
                },
                "action": {"emit": "PAPER_ORDER"},
            }
        ],
    }


def _intent_with_quality(effects: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema": "execution_intent.v1",
        "event_id": "intent_20260215T120000Z",
        "intent": {
            "ts": "20260215T120000Z",
            "execution_mode": "paper",
            "items": [
                {
                    "symbol": "BTCUSDT",
                    "triggered": True,
                    "final_direction": "long",
                    "final_risk_level": "medium",
                    "final_confidence": 0.8,
                    "final_score": 80,
                    "oi_delta_pct": 0.0,
                    "quality": {
                        "mode": "soft_gate",
                        "severity_max": "warn",
                        "effects": effects,
                    },
                }
            ],
        },
    }


def _run(tmp_path: Path, intent_obj: Dict[str, Any]) -> Dict[str, Any]:
    policy_path = tmp_path / "policy.yaml"
    intent_path = tmp_path / "intent.json"
    outbox = tmp_path / "outbox"
    _write_json(policy_path, _policy())
    _write_json(intent_path, intent_obj)
    sha = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    proc = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--execution-intent",
            str(intent_path),
            "--outbox",
            str(outbox),
            "--policy-file",
            str(policy_path),
            "--policy-sha256",
            sha,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    out_path = outbox / "paper_20260215T120000Z.json"
    return json.loads(out_path.read_text(encoding="utf-8"))


def test_observer_default_no_change(tmp_path: Path) -> None:
    out = _run(
        tmp_path,
        _intent_with_quality(
            {
                "size_multiplier": 1.0,
                "reduce_only": False,
                "new_entries_allowed": True,
                "deny": False,
            }
        ),
    )
    orders = out["intent"]["orders"]
    assert len(orders) == 1
    assert orders[0]["sizing"]["equity_pct"] == 0.02
    assert orders[0]["order_meta"]["size_multiplier_applied"] == 1.0


def test_soft_gate_warn_halves_size(tmp_path: Path) -> None:
    out = _run(
        tmp_path,
        _intent_with_quality(
            {
                "size_multiplier": 0.5,
                "reduce_only": False,
                "new_entries_allowed": True,
                "deny": False,
            }
        ),
    )
    orders = out["intent"]["orders"]
    assert len(orders) == 1
    assert orders[0]["sizing"]["equity_pct"] == 0.01
    assert orders[0]["order_meta"]["size_multiplier_applied"] == 0.5


def test_soft_gate_error_blocks_new_entries(tmp_path: Path) -> None:
    out = _run(
        tmp_path,
        _intent_with_quality(
            {
                "size_multiplier": 0.3,
                "reduce_only": True,
                "new_entries_allowed": False,
                "deny": False,
            }
        ),
    )
    assert out["intent"]["orders"] == []


def test_hard_gate_deny_blocks_orders(tmp_path: Path) -> None:
    out = _run(
        tmp_path,
        _intent_with_quality(
            {
                "size_multiplier": 1.0,
                "reduce_only": True,
                "new_entries_allowed": False,
                "deny": True,
            }
        ),
    )
    assert out["intent"]["orders"] == []
