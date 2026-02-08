import re, yaml

def load_policy(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def gate(policy: dict, user_text: str, proposed_action=None):
    findings = []

    for rule in policy.get("rules", []):
        for p in rule.get("deny_patterns", []):
            if re.search(p, user_text, flags=re.IGNORECASE):
                findings.append({"rule": rule["id"], "pattern": p})

    if proposed_action is not None:
        allowed = set()
        for rule in policy.get("rules", []):
            for a in rule.get("allow_actions", []):
                allowed.add(a)
        if proposed_action not in allowed:
            findings.append({"rule": "allowed_actions_only", "action": proposed_action})

    if findings:
        return False, {"decision": "DENY", "findings": findings}

    return True, {"decision": "ALLOW", "findings": []}
