import yaml

def load_rules(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def evaluate(dry, ruleset):
    for rule in ruleset.get("rules", []):
        cond = rule.get("condition", {})

        if "risk_level" in cond:
            if dry.get("risk_level") == cond["risk_level"]:
                return {
                    "decision": rule["action"]["decision"],
                    "reason_codes": [rule["action"]["reason_code"]],
                    "override_required": True,
                    "policy_id": rule["id"],
                    "policy_version": ruleset.get("version"),
                }

        if "confidence_lt" in cond:
            if dry.get("confidence", 1.0) < cond["confidence_lt"]:
                return {
                    "decision": rule["action"]["decision"],
                    "reason_codes": [rule["action"]["reason_code"]],
                    "override_required": True,
                    "policy_id": rule["id"],
                    "policy_version": ruleset.get("version"),
                }

    # default
    defaults = ruleset.get("defaults", {})
    return {
        "decision": defaults.get("decision", "APPROVE"),
        "reason_codes": [],
        "override_required": defaults.get("override_required", False),
        "policy_id": "DEFAULT",
        "policy_version": ruleset.get("version"),
    }
