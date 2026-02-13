import argparse
import json
from pathlib import Path
import yaml

from core.policy_engine import evaluate
from sdk.validate_v1 import (
    validate_normalized_input_v1,
    validate_policy_ruleset_v1,
    validate_gate_decision_v1,
)

def load_yaml(p: Path):
    return yaml.safe_load(p.read_text(encoding="utf-8"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="normalized_input.v1.json path")
    ap.add_argument("--policy", required=True, help="policy yaml path")
    ap.add_argument("--out", required=True, help="output decision json path")
    args = ap.parse_args()

    inp = json.loads(Path(args.input).read_text(encoding="utf-8"))
    validate_normalized_input_v1(inp)

    ruleset = load_yaml(Path(args.policy))
    validate_policy_ruleset_v1(ruleset)

    # Engine consumes feature dict
    features = inp.get("features", {})
    decision = evaluate(features, ruleset)

    # Ensure output conforms to v1 surface
    validate_gate_decision_v1(decision)

    Path(args.out).write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OK: wrote", args.out)

if __name__ == "__main__":
    main()
