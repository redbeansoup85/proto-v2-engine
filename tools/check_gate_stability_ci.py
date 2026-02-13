#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from core.policy_engine import evaluate

ROOT = Path(__file__).resolve().parents[1]

def load_rules(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main() -> int:
    policy_path = Path(os.environ.get("AURALIS_GATE_RULESET", str(ROOT / "policies/sentinel/gate_v1.yaml")))
    if not policy_path.exists():
        raise SystemExit(f"missing ruleset: {policy_path}")

    ruleset = load_rules(policy_path)

    # Two deterministic DRY_RUN fixtures
    a = {
        "intent": "LONG",
        "confidence": 0.80,
        "risk_level": "MEDIUM",
        "policy_refs": ["CI_FIXTURE"],
        "mode": "DRY_RUN",
        "engine_version": "3.0",
        "features": {"funding": 0.0, "open_interest": 0.0},
    }
    b = {
        "intent": "SHORT",
        "confidence": 0.85,
        "risk_level": "MEDIUM",
        "policy_refs": ["CI_FIXTURE"],
        "mode": "DRY_RUN",
        "engine_version": "3.0",
        "features": {"funding": 0.0, "open_interest": 0.0},
    }

    gate_a = evaluate(a.get("features", {}), ruleset)
    gate_b = evaluate(b.get("features", {}), ruleset)

    print("REPLAY_RESULT:")
    print(json.dumps({"run_id": "ci-A", "dry_run": a, "gate": gate_a}, ensure_ascii=False, indent=2))
    print("REPLAY_RESULT:")
    print(json.dumps({"run_id": "ci-B", "dry_run": b, "gate": gate_b}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
