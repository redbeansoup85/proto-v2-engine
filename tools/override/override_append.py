from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.override.schema_override_event import (  # noqa: E402
    canonical_json,
    sha256_hex,
    validate_override_event_full,
    validate_override_event_prechain,
)

PREFIX_MAP = {
    "OVERRIDE_REQUESTED": "ovr_req_",
    "OVERRIDE_APPROVED": "ovr_appr_",
    "OVERRIDE_REJECTED": "ovr_rej_",
    "OVERRIDE_EXECUTED": "ovr_exec_",
}



def _exit2(msg: str) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(2)



def _require(cond: bool, msg: str) -> None:
    if not cond:
        _exit2("CONTRACT_FAIL: " + msg)



def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-jsonl")
    ap.add_argument("--type")
    ap.add_argument("--ts")
    ap.add_argument("--actor-role")
    ap.add_argument("--actor-subject")
    ap.add_argument("--policy-sha256")
    ap.add_argument("--target-decision-event-id")
    ap.add_argument("--target-decision-hash")
    ap.add_argument("--evidence-ref", action="append", default=[])

    ap.add_argument("--requested-action")
    ap.add_argument("--reason-code")
    ap.add_argument("--reason-text")
    ap.add_argument("--ttl-sec", type=int)

    ap.add_argument("--ref-request-event-id")
    ap.add_argument("--scope", action="append", default=[])
    ap.add_argument("--expires-at")
    ap.add_argument("--max-notional", type=float)
    ap.add_argument("--notes")

    ap.add_argument("--rejection-notes")

    ap.add_argument("--ref-approval-event-id")
    ap.add_argument("--effect")
    ap.add_argument("--execution-intent-id")
    return ap.parse_args()



def _event_id(event_type: str, ts: str, actor_subject: str, target_decision_hash: str) -> str:
    base = f"{event_type}|{ts}|{actor_subject}|{target_decision_hash}"
    suffix = sha256_hex(base)[:24]
    return PREFIX_MAP[event_type] + suffix



def _last_nonempty_line(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError as e:
        _exit2(f"IO_FAIL: {e}")
    for line in reversed(lines):
        if line.strip():
            return line
    return None



def _build_event(args: argparse.Namespace) -> dict:
    common = [
        "audit_jsonl",
        "type",
        "ts",
        "actor_role",
        "actor_subject",
        "policy_sha256",
        "target_decision_event_id",
        "target_decision_hash",
    ]
    for field in common:
        _require(getattr(args, field) not in (None, ""), f"missing required arg --{field.replace('_', '-')}")

    _require(len(args.evidence_ref) >= 1, "--evidence-ref required at least once")

    _require(args.type in PREFIX_MAP, "invalid --type")

    ev = {
        "type": args.type,
        "ts": args.ts,
        "event_id": _event_id(args.type, args.ts, args.actor_subject, args.target_decision_hash),
        "actor": {
            "role": args.actor_role,
            "subject": args.actor_subject,
        },
        "policy_sha256": args.policy_sha256,
        "target": {
            "decision_event_id": args.target_decision_event_id,
            "decision_hash": args.target_decision_hash,
        },
        "evidence_refs": args.evidence_ref,
        "chain": {},
        "auth": None,
    }

    if args.type == "OVERRIDE_REQUESTED":
        _require(args.requested_action not in (None, ""), "missing required arg --requested-action")
        _require(args.reason_code not in (None, ""), "missing required arg --reason-code")
        _require(args.reason_text not in (None, ""), "missing required arg --reason-text")
        _require(args.ttl_sec is not None, "missing required arg --ttl-sec")
        ev["request"] = {
            "requested_action": args.requested_action,
            "reason_code": args.reason_code,
            "reason_text": args.reason_text,
            "ttl_sec": args.ttl_sec,
        }
    elif args.type == "OVERRIDE_APPROVED":
        _require(args.ref_request_event_id not in (None, ""), "missing required arg --ref-request-event-id")
        _require(len(args.scope) >= 1, "--scope required at least once")
        _require(args.expires_at not in (None, ""), "missing required arg --expires-at")
        _require(args.max_notional is not None, "missing required arg --max-notional")
        ev["ref_request_event_id"] = args.ref_request_event_id
        constraints = {
            "scope": args.scope,
            "expires_at": args.expires_at,
            "max_notional": args.max_notional,
        }
        if args.notes is not None:
            constraints["notes"] = args.notes
        ev["approval"] = {"decision": "approved", "constraints": constraints}
    elif args.type == "OVERRIDE_REJECTED":
        _require(args.ref_request_event_id not in (None, ""), "missing required arg --ref-request-event-id")
        ev["ref_request_event_id"] = args.ref_request_event_id
        approval = {"decision": "rejected"}
        if args.rejection_notes is not None:
            approval["notes"] = args.rejection_notes
        ev["approval"] = approval
    elif args.type == "OVERRIDE_EXECUTED":
        _require(args.ref_request_event_id not in (None, ""), "missing required arg --ref-request-event-id")
        _require(args.ref_approval_event_id not in (None, ""), "missing required arg --ref-approval-event-id")
        _require(args.effect not in (None, ""), "missing required arg --effect")
        _require(args.execution_intent_id not in (None, ""), "missing required arg --execution-intent-id")
        ev["ref_request_event_id"] = args.ref_request_event_id
        ev["ref_approval_event_id"] = args.ref_approval_event_id
        ev["execution"] = {
            "effect": args.effect,
            "execution_intent_id": args.execution_intent_id,
        }

    return ev



def append_event(audit_jsonl: str, ev: dict) -> dict:
    ev = copy.deepcopy(ev)
    if "auth" not in ev:
        ev["auth"] = None

    last = _last_nonempty_line(audit_jsonl)
    if last is None:
        prev_hash = "GENESIS"
    else:
        try:
            last_ev = json.loads(last)
        except Exception as e:
            _exit2(f"IO_FAIL: invalid json in existing audit file: {e}")
        try:
            prev_hash = last_ev["chain"]["hash"]
        except Exception:
            _exit2("IO_FAIL: existing audit file missing chain.hash")

    ev["chain"] = {"prev_hash": prev_hash, "hash": ""}

    try:
        validate_override_event_prechain(ev)
    except SystemExit as e:
        if isinstance(e.code, str):
            _exit2(e.code)
        raise

    payload_subset = copy.deepcopy(ev)
    if "chain" in payload_subset and isinstance(payload_subset["chain"], dict):
        payload_subset["chain"].pop("hash", None)

    payload_digest = sha256_hex(canonical_json(payload_subset))
    chain_hash = sha256_hex(prev_hash + ":" + payload_digest)
    ev["chain"]["hash"] = chain_hash

    try:
        validate_override_event_full(ev)
    except SystemExit as e:
        if isinstance(e.code, str):
            _exit2(e.code)
        raise

    parent = os.path.dirname(audit_jsonl)
    if parent:
        try:
            os.makedirs(parent, exist_ok=True)
        except OSError as e:
            _exit2(f"IO_FAIL: {e}")

    try:
        with open(audit_jsonl, "a", encoding="utf-8") as f:
            f.write(canonical_json(ev) + "\n")
    except OSError as e:
        _exit2(f"IO_FAIL: {e}")

    return ev



def main() -> None:
    try:
        args = _parse_args()
        ev = _build_event(args)
        out = append_event(args.audit_jsonl, ev)
        print(
            f"OK: appended {out['event_id']} hash={out['chain']['hash']} prev={out['chain']['prev_hash']}"
        )
    except SystemExit as e:
        if isinstance(e.code, int):
            raise
        _exit2(str(e.code))
    except OSError as e:
        _exit2(f"IO_FAIL: {e}")
    except Exception as e:
        _exit2(f"CONTRACT_FAIL: {e}")


if __name__ == "__main__":
    main()
