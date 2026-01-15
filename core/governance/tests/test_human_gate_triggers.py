from core.governance.proposal_validator import validate_proposal_schema
from core.governance.human_gate import evaluate_human_gate


def test_human_gate_external_blast_radius_triggers():
    raw = {
        "proposal_id": "uuid-2",
        "proposal_type": "policy_patch",
        "source": {"kind": "learning", "name": "learner", "run_id": "run-2", "created_at": "2026-01-07T00:00:00Z"},
        "scope": {"domain": "policy", "subsystem": "x", "severity": "high", "blast_radius": "external"},
        "preconditions": {
            "constitution": {"required_sections": ["AQ"], "constitution_hash": "h"},
            "observation_window": {"mode": "time", "t_window": "7d"},
            "sample": {"n_min": 10, "n_observed": 10},
            "stability": {"k_confirmations": 3, "epsilon": 0.1, "summary": "stable enough"},
        },
        "baseline": {"policy_snapshot_id": "snap-1", "policy_hash": "ph"},
        "patch": {"format": "jsonpatch", "content": []},
        "explain": {
            "current_policy_summary": "a",
            "proposed_policy_summary": "b",
            "rationale": "c",
            "expected_impact": "d",
            "rollback_scope": "e",
            "risks": ["reputation risk"],
            "assumptions": [],
            "evidence_refs": ["ev-1"],
        },
        "rate_limit": {"period": "7d", "limit_x": 1, "cooldown": "7d", "rest_required": False},
        "human_gate": {"required": True, "reasons": ["EXTERNAL_REAL_WORLD_EFFECT"]},
    }
    p = validate_proposal_schema(raw)
    required, reasons = evaluate_human_gate(p)
    assert required is True
    assert len(reasons) >= 1
