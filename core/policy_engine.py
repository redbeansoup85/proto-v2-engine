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

def evaluate(features: Dict[str, Any], ruleset: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic policy evaluation.
    reason_codes are policy traces (NOT model explanations).
    """

    for rule in ruleset.get("rules", []):
        cond = rule.get("condition", {}) or {}

        if "risk_level" in cond:
            if features.get("risk_level") == cond["risk_level"]:
                return {
                    "decision": rule["action"]["decision"],
                    "reason_codes": [rule["action"].get("reason_code") or "UNSPECIFIED"],
                    "override_required": True,
                    "policy_id": rule["id"],
                    "policy_version": ruleset.get("version") or "1.0",
                }

        if "confidence_lt" in cond:
            v = _num(cond.get("confidence_lt"), None)
            fv = _num(features.get("confidence"), 1.0)
            if v is not None and fv is not None and fv < v:
                return {
                    "decision": rule["action"]["decision"],
                    "reason_codes": [rule["action"].get("reason_code") or "UNSPECIFIED"],
                    "override_required": True,
                    "policy_id": rule["id"],
                    "policy_version": ruleset.get("version") or "1.0",
                }

        if "funding_gt" in cond:
            v = _num(cond.get("funding_gt"), None)
            fv = _num(features.get("funding"), None)
            if v is not None and fv is not None and fv > v:
                return {
                    "decision": rule["action"]["decision"],
                    "reason_codes": [rule["action"].get("reason_code") or "UNSPECIFIED"],
                    "override_required": True,
                    "policy_id": rule["id"],
                    "policy_version": ruleset.get("version") or "1.0",
                }

        if "open_interest_lt" in cond:
            v = _num(cond.get("open_interest_lt"), None)
            fv = _num(features.get("open_interest"), None)
            if v is not None and fv is not None and fv < v:
                return {
                    "decision": rule["action"]["decision"],
                    "reason_codes": [rule["action"].get("reason_code") or "UNSPECIFIED"],
                    "override_required": True,
                    "policy_id": rule["id"],
                    "policy_version": ruleset.get("version") or "1.0",
                }

    # DEFAULT PATH (deterministic, never empty)
    defaults = ruleset.get("defaults", {}) or {}
    decision = defaults.get("decision", "APPROVE")
    override_required = defaults.get("override_required", False)

    reason_codes: list[str] = []
    reason_codes.append(f"DEFAULT_{decision}")

    risk_level = features.get("risk_level")
    if isinstance(risk_level, str) and risk_level:
        reason_codes.append(f"RISK_{risk_level}")

    mode = features.get("mode")
    if isinstance(mode, str) and mode:
        reason_codes.append(f"MODE_{mode}")

    return {
        "decision": decision,
        "reason_codes": reason_codes,
        "override_required": override_required,
        "policy_id": "DEFAULT",
        "policy_version": ruleset.get("version") or "1.0",
    }
