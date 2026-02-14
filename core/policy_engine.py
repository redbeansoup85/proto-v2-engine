from __future__ import annotations

from typing import Any, Dict
import yaml

def load_rules(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def _num(x: Any, default: float | None = None) -> float | None:
    if isinstance(x, bool):
        return default
    if isinstance(x, (int, float)):
        return float(x)
    return default

def evaluate(dry, ruleset):
    """
    dry: feature dict (e.g. {"x":0.0,"y":0.0})
    ruleset: loaded YAML policy
    """
    for rule in ruleset.get("rules", []):
        cond = rule.get("condition", {})
        action = rule.get("action", {})

        # --- Explicit legacy conditions ---
        if "risk_level" in cond:
            if dry.get("risk_level") == cond["risk_level"]:
                return {
                    "decision": action["decision"],
                    "reason_codes": [action.get("reason_code", "RULE_MATCH")],
                    "override_required": action.get("override_required", True),
                    "policy_id": rule["id"],
                    "policy_version": ruleset.get("version") or "1.0",
                }

        if "confidence_lt" in cond:
            if dry.get("confidence", 1.0) < cond["confidence_lt"]:
                return {
                    "decision": action["decision"],
                    "reason_codes": [action.get("reason_code", "RULE_MATCH")],
                    "override_required": action.get("override_required", True),
                    "policy_id": rule["id"],
                    "policy_version": ruleset.get("version") or "1.0",
                }

        # --- Generic exact match for remaining keys ---
        known = {"risk_level", "confidence_lt"}
        generic_keys = [k for k in cond.keys() if k not in known]

        if generic_keys:
            ok = True
            for k in generic_keys:
                if dry.get(k) != cond[k]:
                    ok = False
                    break
            if ok:
                return {
                    "decision": action["decision"],
                    "reason_codes": [action.get("reason_code", "RULE_MATCH")],
                    "override_required": action.get("override_required", True),
                    "policy_id": rule["id"],
                    "policy_version": ruleset.get("version") or "1.0",
                }

    # --- DEFAULT ---
    defaults = ruleset.get("defaults", {})
    override_required = defaults.get("override_required", False)

    return {
        "decision": defaults.get("decision", "APPROVE"),
        "reason_codes": ["DEFAULT_APPROVE"],
        "override_required": override_required,
        "policy_id": "DEFAULT",
        "policy_version": ruleset.get("version") or "1.0",
    }

