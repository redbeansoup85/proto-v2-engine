from __future__ import annotations

import json
import sys
from datetime import datetime


EVENT_TYPES = {
    "OVERRIDE_REQUESTED",
    "OVERRIDE_APPROVED",
    "OVERRIDE_REJECTED",
    "OVERRIDE_EXECUTED",
}

ACTOR_ROLES = {"operator", "approver", "policy_admin", "auditor"}

REQUESTED_ACTIONS = {
    "block_execution",
    "force_flat",
    "reduce_risk",
    "manual_direction",
}

REASON_CODES = {
    "ANOMALY_DETECTED",
    "POLICY_EXCEPTION",
    "DATA_QUALITY",
    "HUMAN_JUDGMENT",
    "OTHER",
}

EXECUTION_EFFECTS = {"blocked", "flattened", "risk_reduced", "manual_applied"}



def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)



def sha256_hex(s: str) -> str:
    import hashlib

    return hashlib.sha256(s.encode("utf-8")).hexdigest()



def is_hex64(s: str) -> bool:
    if not isinstance(s, str) or len(s) != 64:
        return False
    return all(ch in "0123456789abcdefABCDEF" for ch in s)



def require(cond: bool, msg: str) -> None:
    if not cond:
        print("CONTRACT_FAIL: " + msg, file=sys.stderr)
        raise SystemExit(2)



def validate_isoz(ts: str) -> None:
    require(isinstance(ts, str) and ts.endswith("Z"), "invalid isoz timestamp")
    try:
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        print("CONTRACT_FAIL: invalid isoz timestamp", file=sys.stderr)
        raise SystemExit(2)



def _require_nonempty_str(v, msg: str) -> None:
    require(isinstance(v, str) and v != "", msg)



def _require_number(v, msg: str) -> None:
    require(isinstance(v, (int, float)) and not isinstance(v, bool), msg)



def _validate_actor(actor: dict) -> None:
    require(isinstance(actor, dict), "actor must be object")
    role = actor.get("role")
    subject = actor.get("subject")
    require(role in ACTOR_ROLES, "invalid actor.role")
    _require_nonempty_str(subject, "actor.subject required")



def _validate_target(target: dict) -> None:
    require(isinstance(target, dict), "target must be object")
    _require_nonempty_str(target.get("decision_event_id"), "target.decision_event_id required")
    decision_hash = target.get("decision_hash")
    require(is_hex64(decision_hash), "target.decision_hash must be hex64")



def _validate_evidence_refs(evidence_refs) -> None:
    require(isinstance(evidence_refs, list) and len(evidence_refs) >= 1, "evidence_refs must be non-empty list")
    for ref in evidence_refs:
        _require_nonempty_str(ref, "evidence_refs entries must be non-empty strings")



def _validate_chain_pre(chain: dict) -> None:
    require(isinstance(chain, dict), "chain must be object")
    prev_hash = chain.get("prev_hash")
    require(prev_hash == "GENESIS" or is_hex64(prev_hash), "chain.prev_hash invalid")



def _validate_auth(auth) -> None:
    if auth is None:
        return
    require(isinstance(auth, dict), "auth must be object or null")
    _require_nonempty_str(auth.get("algorithm"), "auth.algorithm required")
    _require_nonempty_str(auth.get("key_id"), "auth.key_id required")
    _require_nonempty_str(auth.get("signature"), "auth.signature required")
    validate_isoz(auth.get("signed_at"))



def _validate_requested(ev: dict) -> None:
    request = ev.get("request")
    require(isinstance(request, dict), "request required")
    require(request.get("requested_action") in REQUESTED_ACTIONS, "invalid request.requested_action")
    require(request.get("reason_code") in REASON_CODES, "invalid request.reason_code")
    _require_nonempty_str(request.get("reason_text"), "request.reason_text required")
    ttl_sec = request.get("ttl_sec")
    require(isinstance(ttl_sec, int) and not isinstance(ttl_sec, bool), "request.ttl_sec must be int")
    require(60 <= ttl_sec <= 86400, "request.ttl_sec out of range")



def _validate_approval_or_rejected(ev: dict) -> None:
    etype = ev.get("type")
    _require_nonempty_str(ev.get("ref_request_event_id"), "ref_request_event_id required")
    approval = ev.get("approval")
    require(isinstance(approval, dict), "approval required")
    decision = approval.get("decision")

    if etype == "OVERRIDE_APPROVED":
        require(decision == "approved", "approval.decision must be approved")
        constraints = approval.get("constraints")
        require(isinstance(constraints, dict), "approval.constraints required")
        scope = constraints.get("scope")
        require(isinstance(scope, list) and len(scope) >= 1, "approval.constraints.scope must be non-empty list")
        for sym in scope:
            _require_nonempty_str(sym, "approval.constraints.scope entries must be non-empty")
        validate_isoz(constraints.get("expires_at"))
        max_notional = constraints.get("max_notional")
        _require_number(max_notional, "approval.constraints.max_notional must be number")
        require(max_notional >= 0, "approval.constraints.max_notional must be >= 0")
        notes = constraints.get("notes")
        if notes is not None:
            require(isinstance(notes, str), "approval.constraints.notes must be string")
    else:
        require(decision == "rejected", "approval.decision must be rejected")
        constraints = approval.get("constraints")
        require(constraints is None or "constraints" not in approval, "rejected approval must not have constraints")
        notes = approval.get("notes")
        if notes is not None:
            require(isinstance(notes, str), "approval.notes must be string")



def _validate_executed(ev: dict) -> None:
    _require_nonempty_str(ev.get("ref_request_event_id"), "ref_request_event_id required")
    _require_nonempty_str(ev.get("ref_approval_event_id"), "ref_approval_event_id required")
    execution = ev.get("execution")
    require(isinstance(execution, dict), "execution required")
    require(execution.get("effect") in EXECUTION_EFFECTS, "invalid execution.effect")
    _require_nonempty_str(execution.get("execution_intent_id"), "execution.execution_intent_id required")



def validate_override_event_prechain(ev: dict) -> None:
    require(isinstance(ev, dict), "event must be object")
    required_top = [
        "type",
        "ts",
        "event_id",
        "actor",
        "policy_sha256",
        "target",
        "evidence_refs",
        "chain",
        "auth",
    ]
    for k in required_top:
        require(k in ev, f"missing required field: {k}")

    etype = ev.get("type")
    require(etype in EVENT_TYPES, "invalid type")
    validate_isoz(ev.get("ts"))
    _require_nonempty_str(ev.get("event_id"), "event_id required")

    _validate_actor(ev.get("actor"))

    policy_sha = ev.get("policy_sha256")
    require(is_hex64(policy_sha), "policy_sha256 must be hex64")

    _validate_target(ev.get("target"))
    _validate_evidence_refs(ev.get("evidence_refs"))
    _validate_chain_pre(ev.get("chain"))
    _validate_auth(ev.get("auth"))

    if etype == "OVERRIDE_REQUESTED":
        _validate_requested(ev)
    elif etype in {"OVERRIDE_APPROVED", "OVERRIDE_REJECTED"}:
        _validate_approval_or_rejected(ev)
    elif etype == "OVERRIDE_EXECUTED":
        _validate_executed(ev)



def validate_override_event_full(ev: dict) -> None:
    validate_override_event_prechain(ev)
    chain = ev.get("chain")
    require(isinstance(chain, dict), "chain must be object")
    require("hash" in chain, "chain.hash required")
    require(is_hex64(chain.get("hash")), "chain.hash must be hex64")
