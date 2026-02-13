from __future__ import annotations
from typing import Any, Dict, List

ALLOWED_DOMAINS = {"SENTINEL", "AURALIS"}
ALLOWED_DECISIONS = {"APPROVE", "REJECT"}

def _fail(msg: str) -> None:
    raise SystemExit(f"FAIL-CLOSED: {msg}")

def _is_str(x: Any) -> bool:
    return isinstance(x, str)

def _is_bool(x: Any) -> bool:
    return isinstance(x, bool)

def _is_num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)

def validate_normalized_input_v1(inp: Dict[str, Any]) -> None:
    if not isinstance(inp, dict):
        _fail("normalized_input must be an object")

    for k in ("input_id", "domain", "ts", "features"):
        if k not in inp:
            _fail(f"normalized_input missing required field: {k}")

    if not _is_str(inp["input_id"]) or not inp["input_id"]:
        _fail("normalized_input.input_id must be non-empty string")

    if inp["domain"] not in ALLOWED_DOMAINS:
        _fail(f"normalized_input.domain must be one of {sorted(ALLOWED_DOMAINS)}")

    if not _is_str(inp["ts"]) or not inp["ts"]:
        _fail("normalized_input.ts must be non-empty string (ISO recommended)")

    if not isinstance(inp["features"], dict):
        _fail("normalized_input.features must be an object")

def validate_policy_ruleset_v1(ruleset: Dict[str, Any]) -> None:
    if not isinstance(ruleset, dict):
        _fail("policy ruleset must be an object")

    for k in ("version", "name", "rules", "defaults"):
        if k not in ruleset:
            _fail(f"policy ruleset missing required field: {k}")

    if not _is_str(ruleset["version"]) or not ruleset["version"]:
        _fail("policy.version must be non-empty string")

    if not _is_str(ruleset["name"]) or not ruleset["name"]:
        _fail("policy.name must be non-empty string")

    rules = ruleset["rules"]
    if not isinstance(rules, list):
        _fail("policy.rules must be an array")

    defaults = ruleset["defaults"]
    if not isinstance(defaults, dict):
        _fail("policy.defaults must be an object")

    if defaults.get("decision") not in ALLOWED_DECISIONS:
        _fail(f"policy.defaults.decision must be one of {sorted(ALLOWED_DECISIONS)}")

    if "override_required" not in defaults or not _is_bool(defaults["override_required"]):
        _fail("policy.defaults.override_required must be boolean")

    # Validate each rule
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict):
            _fail(f"policy.rules[{i}] must be object")

        for k in ("id", "condition", "action"):
            if k not in rule:
                _fail(f"policy.rules[{i}] missing field: {k}")

        if not _is_str(rule["id"]) or not rule["id"]:
            _fail(f"policy.rules[{i}].id must be non-empty string")

        if not isinstance(rule["condition"], dict):
            _fail(f"policy.rules[{i}].condition must be object")

        action = rule["action"]
        if not isinstance(action, dict):
            _fail(f"policy.rules[{i}].action must be object")

        if action.get("decision") not in ALLOWED_DECISIONS:
            _fail(f"policy.rules[{i}].action.decision must be one of {sorted(ALLOWED_DECISIONS)}")

        # reason_code: string or null
        rc = action.get("reason_code", None)
        if rc is not None and not _is_str(rc):
            _fail(f"policy.rules[{i}].action.reason_code must be string or null")

        # Supported conditions (fail-closed on unknown condition keys)
        allowed_cond_keys = {"risk_level", "confidence_lt"}
        unknown = set(rule["condition"].keys()) - allowed_cond_keys
        if unknown:
            _fail(f"policy.rules[{i}] has unknown condition keys: {sorted(unknown)}")

        if "confidence_lt" in rule["condition"]:
            v = rule["condition"]["confidence_lt"]
            if not _is_num(v):
                _fail(f"policy.rules[{i}].condition.confidence_lt must be number")

def validate_gate_decision_v1(dec: Dict[str, Any]) -> None:
    if not isinstance(dec, dict):
        _fail("gate_decision must be an object")

    for k in ("decision", "reason_codes", "override_required", "policy_id", "policy_version"):
        if k not in dec:
            _fail(f"gate_decision missing required field: {k}")

    if dec["decision"] not in ALLOWED_DECISIONS:
        _fail(f"gate_decision.decision must be one of {sorted(ALLOWED_DECISIONS)}")

    if not isinstance(dec["reason_codes"], list) or any(not _is_str(x) for x in dec["reason_codes"]):
        _fail("gate_decision.reason_codes must be array of strings")

    if not _is_bool(dec["override_required"]):
        _fail("gate_decision.override_required must be boolean")

    if not _is_str(dec["policy_id"]) or not dec["policy_id"]:
        _fail("gate_decision.policy_id must be non-empty string")

    if not _is_str(dec["policy_version"]) or not dec["policy_version"]:
        _fail("gate_decision.policy_version must be non-empty string")

    # Optional: policy_sha256
    if "policy_sha256" in dec and (not _is_str(dec["policy_sha256"]) or not dec["policy_sha256"]):
        _fail("gate_decision.policy_sha256 must be non-empty string when provided")

    # Optional: policy_capsule_sha256
    if "policy_capsule_sha256" in dec and (not _is_str(dec["policy_capsule_sha256"]) or not dec["policy_capsule_sha256"]):
        _fail("gate_decision.policy_capsule_sha256 must be non-empty string when provided")

    # Optional: policy_capsule
    if "policy_capsule" in dec and not isinstance(dec["policy_capsule"], dict):
        _fail("gate_decision.policy_capsule must be object when provided")
