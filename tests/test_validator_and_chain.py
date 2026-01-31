from core.hasher import compute_payload_hash, compute_event_id
from core.validator import KNOWN_SCHEMA_HASH
from core.validator import KNOWN_SCHEMA_HASH
from core.validator import validate_core_event_fail_closed
from core.chain_walker import walk_and_verify_chain

# 테스트용 상수(운영에서는 실제 LOCK schema_hash로 치환)

def build_event(event_type: str, payload: dict, *, seq: int, prev_event_id=None):
    artifact_refs = {
        "execution_card_id": "SEC-TEST-001",
        "parent_card_id": None,
        "policy_id": None,
        "run_id": "RUN-TEST-001",
        "approval_id": None,
    }

    payload_hash = compute_payload_hash(payload)
    event_id = compute_event_id(
        event_type=event_type,
        system_id="Sentinel",
        domain="trading",
        asset_or_subject_id="SOLUSDT",
        chain_snapshot_id="chain-001",
        sequence_no=seq,
        artifact_refs=artifact_refs,
        payload_hash=payload_hash,
    )

    return {
        "event_envelope": {
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at_utc": "2026-01-22T00:00:00Z",
            "produced_at_utc": "2026-01-22T00:00:01Z",
            "system_id": "Sentinel",
            "domain": "trading",
            "asset_or_subject_id": "SOLUSDT",
            "environment": "shadow",
            "classification": "internal",
            "chain": {
                "chain_snapshot_id": "chain-001",
                "prev_event_id": prev_event_id,
                "sequence_no": seq,
            },
            "actor": {
                "actor_type": "service",
                "actor_id": "svc-01",
                "auth_context_id": None,
            },
            "artifact_refs": artifact_refs,
            "integrity": {
                "schema_id": "JOS-JUDGMENT-COMMON-v1.0",
                "schema_hash": KNOWN_SCHEMA_HASH,
                "payload_hash": payload_hash,
            },
        },
        "payload": payload,
    }

def test_valid_trading_observation():
    payload = {
        "observation_kind": "signal",
        "inputs": {"source_ids": ["domain/trading/2026-01-22/binance/snap_1.json"], "snapshot_id": "snap-1"},
        "metrics": [{"key": "ICF_COMPOSITE", "value": "78", "unit": "score"}],
        "tags": ["test"],
    }
    ev = build_event("OBSERVATION", payload, seq=1, prev_event_id=None)
    ok, msg = validate_core_event_fail_closed(ev)
    assert ok, msg

def test_fail_float_payload():
    import pytest
    from core.canonical_json import CanonicalJSONError

    payload = {"observation_kind": "signal", "inputs": {"source_ids": []}, "metrics": [{"key": "x", "value": 0.1, "unit": "pct"}]}

    with pytest.raises(CanonicalJSONError):
        _ = build_event("OBSERVATION", payload, seq=1, prev_event_id=None)

def test_chain_walker_prev_link_break():
    p1 = {"observation_kind":"signal","inputs":{"source_ids":[]},"metrics":[{"key":"a","value":"1","unit":"x"}]}
    e1 = build_event("OBSERVATION", p1, seq=1, prev_event_id=None)

    p2 = {"outcome_id":"o1","outcome_kind":"pnl","metrics":[{"key":"realized_pnl","value":"10","unit":"usd"}],"evaluation_window":{"start_utc":"2026-01-22T00:00:00Z","end_utc":"2026-01-22T00:10:00Z"}}
    # prev_event_id intentionally wrong
    e2 = build_event("OUTCOME_RECORDED", p2, seq=2, prev_event_id="sha256:" + "00"*32)

    res = walk_and_verify_chain([e1, e2], strict_contiguous=True)
    assert any((not ok and "prev_event_id mismatch" in msg) for _, ok, msg in res)
