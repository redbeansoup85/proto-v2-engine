from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Tuple
import re

from .hasher import compute_event_id, compute_payload_hash
from .constants import KNOWN_SCHEMA_ID, KNOWN_SCHEMA_HASH

# =========================
# LOCKED CONSTANTS (Phase-1)
# =========================

KNOWN_SCHEMA_HASH = "sha256:023ef3e62f0c31ea2b813c561d413727eebafb7c824d9fe574c4d7b6b5ddb258"

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

VALID_EVENT_TYPES = {
    "OBSERVATION",
    "EXECUTION_REQUESTED",
    "EXECUTION_AUTHORIZED",
    "EXECUTION_BLOCKED",
    "EXECUTION_STARTED",
    "EXECUTION_FILLED",
    "EXECUTION_COMPLETED",
    "INVALIDATION_TRIGGERED",
    "HUMAN_OVERRIDE_APPLIED",
    "OUTCOME_RECORDED",
    "AUDIT_LOGGED",
}

# ==================================
# Helpers (fail-closed, minimal)
# ==================================


def _parse_z(dt: str) -> datetime:
    # Fail-closed: must be ISO8601 with 'Z' or explicit offset
    return datetime.fromisoformat(dt.replace("Z", "+00:00"))


def _require_dict(x: Any, name: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    if not isinstance(x, dict):
        return False, None, f"{name} must be object"
    return True, x, "ok"


def _require_str(x: Any, name: str) -> Tuple[bool, Optional[str], str]:
    if not isinstance(x, str):
        return False, None, f"{name} must be string"
    if x.strip() == "":
        return False, None, f"{name} must be non-empty string"
    return True, x, "ok"


def _require_sha256_prefixed(x: Any, name: str) -> Tuple[bool, Optional[str], str]:
    if not isinstance(x, str):
        return False, None, f"{name} must be string"
    if not _SHA256_RE.match(x):
        return False, None, f"{name} must match sha256:<64hex>"
    return True, x, "ok"


# ==================================
# LOCKED Validator (Phase-1)
# ==================================


def validate_core_event_fail_closed(event: Dict[str, Any]) -> Tuple[bool, str]:
    """
    LOCKED contract validator (Phase-1):
    - event must contain event_envelope + payload
    - schema_id fixed, schema_hash must match KNOWN_SCHEMA_HASH (fail-closed)
    - float forbidden via payload_hash recomputation
    - artifact_refs dict with 5 keys; at least one non-null (except AUDIT_LOGGED)
    - event_id matches deterministic recompute (Option A)
    - minimal event_type payload shape checks
    """
    try:
        ok, env, msg = _require_dict(event.get("event_envelope"), "event_envelope")
        if not ok:
            return False, msg

        ok, payload_obj, msg = _require_dict(event.get("payload"), "payload")
        if not ok:
            return False, msg

        # --- required envelope keys ---
        required_env = [
            "event_id",
            "event_type",
            "occurred_at_utc",
            "produced_at_utc",
            "system_id",
            "domain",
            "asset_or_subject_id",
            "environment",
            "classification",
            "chain",
            "actor",
            "artifact_refs",
            "integrity",
        ]
        missing = [k for k in required_env if k not in env]
        if missing:
            return False, f"missing event_envelope fields: {missing}"

        # --- event_type ---
        event_type = env["event_type"]
        if event_type not in VALID_EVENT_TYPES:
            return False, f"unknown event_type: {event_type}"

        # --- event_id format (sha256:...) ---
        ok, _, msg = _require_sha256_prefixed(env.get("event_id"), "event_envelope.event_id")
        if not ok:
            return False, msg

        # --- system_id / domain / asset_or_subject_id ---
        for field in ("system_id", "domain", "asset_or_subject_id"):
            ok, _, msg = _require_str(env.get(field), f"event_envelope.{field}")
            if not ok:
                return False, msg

        # --- time order ---
        ok, occ, msg = _require_str(env.get("occurred_at_utc"), "event_envelope.occurred_at_utc")
        if not ok:
            return False, msg
        ok, prod, msg = _require_str(env.get("produced_at_utc"), "event_envelope.produced_at_utc")
        if not ok:
            return False, msg

        occ_dt = _parse_z(occ)
        prod_dt = _parse_z(prod)
        if prod_dt < occ_dt:
            return False, "produced_at_utc must be >= occurred_at_utc"

        # --- chain ---
        ok, chain, msg = _require_dict(env["chain"], "event_envelope.chain")
        if not ok:
            return False, msg

        for k in ("chain_snapshot_id", "prev_event_id", "sequence_no"):
            if k not in chain:
                return False, f"missing chain.{k}"

        ok, _, msg = _require_str(chain.get("chain_snapshot_id"), "chain.chain_snapshot_id")
        if not ok:
            return False, msg

        if chain["prev_event_id"] is not None:
            ok, _, msg = _require_str(chain["prev_event_id"], "chain.prev_event_id")
            if not ok:
                return False, "prev_event_id must be string|null"

        if not isinstance(chain["sequence_no"], int) or chain["sequence_no"] < 1:
            return False, "sequence_no must be int >= 1"

        # --- artifact_refs (dict schema, fixed keys) ---
        ok, refs, msg = _require_dict(env["artifact_refs"], "event_envelope.artifact_refs")
        if not ok:
            return False, msg

        ref_keys = ["execution_card_id", "parent_card_id", "policy_id", "run_id", "approval_id"]
        if any(k not in refs for k in ref_keys):
            return False, f"artifact_refs must include keys: {ref_keys}"

        # (Optional) enforce string|null for each ref field
        for k in ref_keys:
            v = refs.get(k)
            if v is not None and not isinstance(v, str):
                return False, f"artifact_refs.{k} must be string|null"

        if event_type != "AUDIT_LOGGED":
            if not any(refs[k] is not None for k in ref_keys):
                return False, "at least one artifact_refs.* must be non-null (except AUDIT_LOGGED)"

        # --- integrity ---
        ok, integ, msg = _require_dict(env["integrity"], "event_envelope.integrity")
        if not ok:
            return False, msg

        for k in ("schema_id", "schema_hash", "payload_hash"):
            if k not in integ:
                return False, f"missing integrity.{k}"

        if integ["schema_id"] != KNOWN_SCHEMA_ID:
            return False, f"schema_id must be {KNOWN_SCHEMA_ID}"

        ok, _, msg = _require_sha256_prefixed(integ.get("schema_hash"), "integrity.schema_hash")
        if not ok:
            return False, msg
        if integ["schema_hash"] != KNOWN_SCHEMA_HASH:
            return False, "schema_hash does not match locked known constant"

        ok, _, msg = _require_sha256_prefixed(integ.get("payload_hash"), "integrity.payload_hash")
        if not ok:
            return False, msg

        # --- payload_hash recompute (also enforces float ban) ---
        computed_ph = compute_payload_hash(payload_obj)
        if integ["payload_hash"] != computed_ph:
            return False, f"payload_hash mismatch (computed {computed_ph})"

        # --- event_id recompute (Option A) ---
        computed_eid = compute_event_id(
            event_type=event_type,
            system_id=env["system_id"],
            domain=env["domain"],
            asset_or_subject_id=env["asset_or_subject_id"],
            chain_snapshot_id=chain["chain_snapshot_id"],
            sequence_no=chain["sequence_no"],
            artifact_refs=refs,
            payload_hash=integ["payload_hash"],
        )
        if env["event_id"] != computed_eid:
            return False, f"event_id mismatch (computed {computed_eid})"

        # --- minimal payload checks ---
        if event_type == "OBSERVATION":
            for k in ("observation_kind", "inputs", "metrics"):
                if k not in payload_obj:
                    return False, f"OBSERVATION payload missing {k}"
        elif event_type == "EXECUTION_REQUESTED":
            for k in ("request_id", "execution_scope", "intent", "constraints"):
                if k not in payload_obj:
                    return False, f"EXECUTION_REQUESTED payload missing {k}"
        elif event_type in ("EXECUTION_AUTHORIZED", "EXECUTION_BLOCKED"):
            for k in ("decision", "reason_codes", "rule_evidence", "required_approvals"):
                if k not in payload_obj:
                    return False, f"{event_type} payload missing {k}"
        elif event_type == "EXECUTION_FILLED":
            for k in ("fill_id", "venue", "side", "linkage"):
                if k not in payload_obj:
                    return False, f"EXECUTION_FILLED payload missing {k}"
        elif event_type == "INVALIDATION_TRIGGERED":
            for k in ("invalidation_id", "invalidation_tag", "trigger_condition", "mandatory_action"):
                if k not in payload_obj:
                    return False, f"INVALIDATION_TRIGGERED payload missing {k}"
        elif event_type == "HUMAN_OVERRIDE_APPLIED":
            for k in ("override_id", "override_type", "scope", "justification"):
                if k not in payload_obj:
                    return False, f"HUMAN_OVERRIDE_APPLIED payload missing {k}"
        elif event_type == "OUTCOME_RECORDED":
            for k in ("outcome_id", "outcome_kind", "metrics", "evaluation_window"):
                if k not in payload_obj:
                    return False, f"OUTCOME_RECORDED payload missing {k}"
        elif event_type == "AUDIT_LOGGED":
            for k in ("audit_id", "audit_kind", "status"):
                if k not in payload_obj:
                    return False, f"AUDIT_LOGGED payload missing {k}"

        return True, "valid"

    except Exception as e:
        # Fail-closed, but keep message stable-ish for tests
        return False, f"validation error: {e}"
