#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

import yaml
from core.policy_engine import evaluate

ROOT = Path(__file__).resolve().parents[1]

def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def main() -> int:
    # Ruleset path (overrideable)
    ruleset_path = Path(os.environ.get("AURALIS_GATE_RULESET", str(ROOT / "policies/sentinel/gate_v1.yaml")))
    if not ruleset_path.exists():
        raise SystemExit(f"missing ruleset: {ruleset_path}")
    ruleset = load_yaml(ruleset_path)

    # Fixture paths (overrideable)
    a_path = Path(os.environ.get("AURALIS_DRYRUN_A", str(ROOT / "tools/fixtures/dry_run_ci_A.json")))
    b_path = Path(os.environ.get("AURALIS_DRYRUN_B", str(ROOT / "tools/fixtures/dry_run_ci_B.json")))
    if not a_path.exists():
        raise SystemExit(f"missing fixture A: {a_path}")
    if not b_path.exists():
        raise SystemExit(f"missing fixture B: {b_path}")

    a = load_json(a_path)
    b = load_json(b_path)

    # Gate evaluation uses deterministic normalized features
    gate_a = evaluate((a.get("features") or {}), ruleset)
    gate_b = evaluate((b.get("features") or {}), ruleset)

    print("REPLAY_RESULT:")
    print(json.dumps({"run_id": "ci-A", "dry_run": a, "gate": gate_a}, ensure_ascii=False, indent=2))
    print("REPLAY_RESULT:")
    print(json.dumps({"run_id": "ci-B", "dry_run": b, "gate": gate_b}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
