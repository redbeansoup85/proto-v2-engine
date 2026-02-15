from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.override.override_registry import build_active_overrides  # noqa: E402
from tools.override.schema_override_event import canonical_json, sha256_hex  # noqa: E402



def _run_verify(audit: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "tools/audit/verify_override_chain.py", "--audit-jsonl", audit],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )



def _mk_base(ts: str, event_id: str, actor_subject: str, etype: str) -> dict:
    return {
        "type": etype,
        "ts": ts,
        "event_id": event_id,
        "actor": {"role": "operator", "subject": actor_subject},
        "policy_sha256": "a" * 64,
        "target": {"decision_event_id": "dec_1", "decision_hash": "b" * 64},
        "evidence_refs": ["evidence:/1"],
        "chain": {},
        "auth": None,
    }



def _chainify(events: list[dict]) -> list[dict]:
    out = []
    prev = "GENESIS"
    for ev in events:
        item = copy.deepcopy(ev)
        item["chain"] = {"prev_hash": prev, "hash": ""}
        payload_subset = copy.deepcopy(item)
        payload_subset["chain"].pop("hash", None)
        payload_digest = sha256_hex(canonical_json(payload_subset))
        ch = sha256_hex(prev + ":" + payload_digest)
        item["chain"]["hash"] = ch
        out.append(item)
        prev = ch
    return out



def _write(audit: str, events: list[dict]) -> None:
    lines = [canonical_json(ev) for ev in events]
    Path(audit).write_text("\n".join(lines) + "\n", encoding="utf-8")



def _assert_fail(audit: str, label: str) -> None:
    cp = _run_verify(audit)
    if cp.returncode == 0:
        raise AssertionError(f"expected failure: {label}")



def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)

        # 1) Missing request
        audit1 = str(td_path / "case1.jsonl")
        appr = _mk_base("2026-02-15T03:34:00Z", "appr_missing_req", "approver-1", "OVERRIDE_APPROVED")
        appr["actor"]["role"] = "approver"
        appr["ref_request_event_id"] = "missing_req"
        appr["approval"] = {
            "decision": "approved",
            "constraints": {
                "scope": ["BTCUSDT"],
                "expires_at": "2026-02-15T05:00:00Z",
                "max_notional": 1000.0,
            },
        }
        _write(audit1, _chainify([appr]))
        _assert_fail(audit1, "missing request")

        # 2) Missing approval for executed
        audit2 = str(td_path / "case2.jsonl")
        req = _mk_base("2026-02-15T03:30:00Z", "req_1", "requester-1", "OVERRIDE_REQUESTED")
        req["request"] = {
            "requested_action": "block_execution",
            "reason_code": "ANOMALY_DETECTED",
            "reason_text": "r",
            "ttl_sec": 300,
        }
        exe = _mk_base("2026-02-15T03:35:00Z", "exec_1", "operator-2", "OVERRIDE_EXECUTED")
        exe["ref_request_event_id"] = "req_1"
        exe["ref_approval_event_id"] = "missing_approval"
        exe["execution"] = {"effect": "blocked", "execution_intent_id": "intent-1"}
        _write(audit2, _chainify([req, exe]))
        _assert_fail(audit2, "missing approval")

        # 3) Expired approval
        audit3 = str(td_path / "case3.jsonl")
        req3 = _mk_base("2026-02-15T03:30:00Z", "req_3", "requester-3", "OVERRIDE_REQUESTED")
        req3["request"] = {
            "requested_action": "reduce_risk",
            "reason_code": "POLICY_EXCEPTION",
            "reason_text": "r3",
            "ttl_sec": 300,
        }
        appr3 = _mk_base("2026-02-15T03:31:00Z", "appr_3", "approver-3", "OVERRIDE_APPROVED")
        appr3["actor"]["role"] = "approver"
        appr3["ref_request_event_id"] = "req_3"
        appr3["approval"] = {
            "decision": "approved",
            "constraints": {
                "scope": ["ETHUSDT"],
                "expires_at": "2026-02-15T03:40:00Z",
                "max_notional": 50.0,
            },
        }
        exe3 = _mk_base("2026-02-15T03:45:00Z", "exec_3", "operator-3", "OVERRIDE_EXECUTED")
        exe3["ref_request_event_id"] = "req_3"
        exe3["ref_approval_event_id"] = "appr_3"
        exe3["execution"] = {"effect": "risk_reduced", "execution_intent_id": "intent-3"}
        _write(audit3, _chainify([req3, appr3, exe3]))
        _assert_fail(audit3, "expired approval")

        # 4) Role separation violation
        audit4 = str(td_path / "case4.jsonl")
        req4 = _mk_base("2026-02-15T03:30:00Z", "req_4", "same-user", "OVERRIDE_REQUESTED")
        req4["request"] = {
            "requested_action": "manual_direction",
            "reason_code": "HUMAN_JUDGMENT",
            "reason_text": "r4",
            "ttl_sec": 300,
        }
        appr4 = _mk_base("2026-02-15T03:31:00Z", "appr_4", "same-user", "OVERRIDE_APPROVED")
        appr4["actor"]["role"] = "approver"
        appr4["ref_request_event_id"] = "req_4"
        appr4["approval"] = {
            "decision": "approved",
            "constraints": {
                "scope": ["SOLUSDT"],
                "expires_at": "2026-02-15T04:30:00Z",
                "max_notional": 1.0,
            },
        }
        _write(audit4, _chainify([req4, appr4]))
        _assert_fail(audit4, "role separation")

        # 5) Active registry latest approval per symbol, expired excluded
        events = []
        req5a = _mk_base("2026-02-15T03:00:00Z", "req_5a", "rq-a", "OVERRIDE_REQUESTED")
        req5a["request"] = {
            "requested_action": "block_execution",
            "reason_code": "DATA_QUALITY",
            "reason_text": "a",
            "ttl_sec": 300,
        }
        appr5a = _mk_base("2026-02-15T03:10:00Z", "appr_5a", "ap-a", "OVERRIDE_APPROVED")
        appr5a["actor"]["role"] = "approver"
        appr5a["ref_request_event_id"] = "req_5a"
        appr5a["approval"] = {
            "decision": "approved",
            "constraints": {
                "scope": ["BTCUSDT"],
                "expires_at": "2026-02-15T06:00:00Z",
                "max_notional": 100.0,
            },
        }

        req5b = _mk_base("2026-02-15T03:20:00Z", "req_5b", "rq-b", "OVERRIDE_REQUESTED")
        req5b["request"] = {
            "requested_action": "reduce_risk",
            "reason_code": "OTHER",
            "reason_text": "b",
            "ttl_sec": 300,
        }
        appr5b = _mk_base("2026-02-15T03:30:00Z", "appr_5b", "ap-b", "OVERRIDE_APPROVED")
        appr5b["actor"]["role"] = "approver"
        appr5b["ref_request_event_id"] = "req_5b"
        appr5b["approval"] = {
            "decision": "approved",
            "constraints": {
                "scope": ["BTCUSDT", "ETHUSDT"],
                "expires_at": "2026-02-15T06:30:00Z",
                "max_notional": 200.0,
            },
        }

        req5c = _mk_base("2026-02-15T02:00:00Z", "req_5c", "rq-c", "OVERRIDE_REQUESTED")
        req5c["request"] = {
            "requested_action": "force_flat",
            "reason_code": "ANOMALY_DETECTED",
            "reason_text": "c",
            "ttl_sec": 300,
        }
        appr5c = _mk_base("2026-02-15T02:10:00Z", "appr_5c", "ap-c", "OVERRIDE_APPROVED")
        appr5c["actor"]["role"] = "approver"
        appr5c["ref_request_event_id"] = "req_5c"
        appr5c["approval"] = {
            "decision": "approved",
            "constraints": {
                "scope": ["XRPUSDT"],
                "expires_at": "2026-02-15T03:00:00Z",
                "max_notional": 300.0,
            },
        }

        events.extend([req5a, appr5a, req5b, appr5b, req5c, appr5c])
        active = build_active_overrides(_chainify(events), "2026-02-15T03:40:00Z")
        if "XRPUSDT" in active:
            raise AssertionError("expired override included")
        if "BTCUSDT" not in active or active["BTCUSDT"]["approval_event_id"] != "appr_5b":
            raise AssertionError("latest approval not selected for BTCUSDT")

    print("SELFTEST_OK_V2")


if __name__ == "__main__":
    main()
