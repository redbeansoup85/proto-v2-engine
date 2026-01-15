import pytest
from core.governance.proposal_validator import validate_proposal_schema


def _minimal_raw():
    return {
        "proposal_id": "uuid-1",
        "proposal_type": "policy_patch",
        "source": {"kind": "learning", "name": "learner", "run_id": "run-1", "created_at": "2026-01-07T00:00:00Z"},
        "scope": {"domain": "policy", "subsystem": "x", "severity": "low", "blast_radius": "local"},
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
            "risks": [],
            "assumptions": [],
            "evidence_refs": [],
        },
        "rate_limit": {"period": "7d", "limit_x": 1, "cooldown": "7d", "rest_required": False},
        "human_gate": {"required": False, "reasons": []},
    }


def test_schema_valid_minimal():
    p = validate_proposal_schema(_minimal_raw())
    assert p.proposal_id == "uuid-1"


def test_explain_non_empty_enforced():
    raw = _minimal_raw()
    raw["explain"]["rationale"] = "   "
    with pytest.raises(Exception):
        validate_proposal_schema(raw)
