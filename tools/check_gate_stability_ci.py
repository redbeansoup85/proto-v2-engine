#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

from sdk.gate_cli import load_rules
from core.policy_engine import evaluate


ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    # default paths (can be overridden by env)
    policy_path = Path(os.environ.get("AURALIS_GATE_RULESET", str(ROOT / "policies/sentinel/gate_v1.yaml")))
    if not policy_path.exists():
        raise SystemExit(f"missing ruleset: {policy_path}")

    ruleset = load_rules(str(policy_path))

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

    # Evaluate gate on deterministic features (policy_engine.evaluate expects features dict)
    gate_a = evaluate(a.get("features", {}), ruleset)
    gate_b = evaluate(b.get("features", {}), ruleset)

    # Print in the exact format expected by tools/check_gate_stability.py
    print("REPLAY_RESULT:")
    print(json.dumps({"run_id": "ci-A", "dry_run": a, "gate": gate_a}, ensure_ascii=False, indent=2))
    print("REPLAY_RESULT:")
    print(json.dumps({"run_id": "ci-B", "dry_run": b, "gate": gate_b}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
