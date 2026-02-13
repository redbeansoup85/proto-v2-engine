#!/usr/bin/env python3
import argparse
import json
import hashlib
from pathlib import Path

import yaml

from sdk.validate_v1 import validate_gate_decision_v1
from core.policy_engine import load_rules, evaluate


def sha256_file(path: str) -> str:
    b = Path(path).read_bytes()
    return hashlib.sha256(b).hexdigest()


def _canonical_sha256(obj) -> str:
    b = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="normalized input json")
    ap.add_argument("--policy", required=True, help="policy yaml path")
    ap.add_argument("--out", required=True, help="output gate decision json")
    args = ap.parse_args()

    inp_path = Path(args.input)
    policy_path = Path(args.policy)
    out_path = Path(args.out)

    dry = json.loads(inp_path.read_text(encoding="utf-8"))
    ruleset = load_rules(str(policy_path))
    decision = evaluate(dry, ruleset)

    # Attach deterministic policy fingerprints
    decision["policy_sha256"] = sha256_file(str(policy_path))

    # Attach policy capsule + digest for strict stability
    policy_capsule = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    decision["policy_capsule"] = policy_capsule
    decision["policy_capsule_sha256"] = _canonical_sha256(policy_capsule)

    # Validate against v1 schema checks (python validator)
    validate_gate_decision_v1(decision)

    out_path.write_text(json.dumps(decision, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK: wrote {out_path}")


if __name__ == "__main__":
    main()
