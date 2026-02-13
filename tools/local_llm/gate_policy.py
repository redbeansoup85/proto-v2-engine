import json
from pathlib import Path
from core.policy_engine import load_rules, evaluate

ROOT = Path(__file__).resolve().parents[2]
DRY_PATH = ROOT / "var/local_llm/dry_run_validated.json"
RULE_PATH = ROOT / "policies/sentinel/gate_v1.yaml"
OUT_PATH = ROOT / "var/local_llm/gate_decision.json"

def main():
    dry = json.loads(DRY_PATH.read_text(encoding="utf-8"))
    ruleset = load_rules(RULE_PATH)
    decision = evaluate(dry, ruleset)

    OUT_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OK: sentinel policy gate written")
    print(json.dumps(decision, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
