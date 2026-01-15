from __future__ import annotations

from core.governance.queue_evaluator import QueueDeps, evaluate_proposal_constitutional
from core.governance.proposal_schema import PolicyProposal


def _proposal_with_baseline(baseline_hash: str) -> PolicyProposal:
    return PolicyProposal.model_validate(
        {
            "proposal_id": "uuid-order-1",
            "proposal_type": "policy_patch",
            "source": {"kind": "learning", "name": "learner", "run_id": "run-ord", "created_at": "2026-01-07T00:00:00Z"},
            "scope": {"domain": "policy", "subsystem": "x", "severity": "low", "blast_radius": "local"},
            "preconditions": {
                "constitution": {"required_sections": ["AQ"], "constitution_hash": "h"},
                "observation_window": {"mode": "time", "t_window": "7d"},
                "sample": {"n_min": 10, "n_observed": 10},
                "stability": {"k_confirmations": 3, "epsilon": 0.1, "summary": "stable enough"},
            },
            "baseline": {"policy_snapshot_id": "snap-1", "policy_hash": baseline_hash},
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
    )


def test_constitutional_order_noop_first():
    calls = []

    # Arrange: make is_noop True, but also make duplicate/mismatch potentially True.
    def is_noop(_p):
        calls.append("noop")
        return True

    def has_applied(_h):
        calls.append("duplicate")
        return True

    def get_current_hash():
        calls.append("current_hash")
        return "CURRENT"

    def apply_patch(_p):
        calls.append("apply")
        return True, "NEW", "patch-1", "APPLIED"

    deps = QueueDeps(
        get_current_policy_hash=get_current_hash,
        has_policy_hash_been_applied=has_applied,
        apply_patch=apply_patch,
        is_noop=is_noop,
    )

    proposal = _proposal_with_baseline("CURRENT")
    out = evaluate_proposal_constitutional(proposal, deps=deps)

    assert out.result.value == "NOOP"
    # Must stop after noop; duplicate/mismatch/apply must not execute.
    assert calls == ["current_hash", "noop"]


def test_constitutional_order_duplicate_before_mismatch():
    calls = []

    def is_noop(_p):
        calls.append("noop")
        return False

    def has_applied(_h):
        calls.append("duplicate")
        return True

    def get_current_hash():
        calls.append("current_hash")
        return "CURRENT"

    def apply_patch(_p):
        calls.append("apply")
        return True, "NEW", "patch-1", "APPLIED"

    deps = QueueDeps(
        get_current_policy_hash=get_current_hash,
        has_policy_hash_been_applied=has_applied,
        apply_patch=apply_patch,
        is_noop=is_noop,
    )

    # Mismatch would be true if checked (baseline != current), but duplicate must short-circuit first.
    proposal = _proposal_with_baseline("BASELINE_DIFFERENT")
    out = evaluate_proposal_constitutional(proposal, deps=deps)

    assert out.result.value == "DUPLICATE"
    assert calls == ["current_hash", "noop", "duplicate"]


def test_constitutional_order_mismatch_before_apply():
    calls = []

    def is_noop(_p):
        calls.append("noop")
        return False

    def has_applied(_h):
        calls.append("duplicate")
        return False

    def get_current_hash():
        calls.append("current_hash")
        return "CURRENT"

    def apply_patch(_p):
        calls.append("apply")
        return True, "NEW", "patch-1", "APPLIED"

    deps = QueueDeps(
        get_current_policy_hash=get_current_hash,
        has_policy_hash_been_applied=has_applied,
        apply_patch=apply_patch,
        is_noop=is_noop,
    )

    # Baseline mismatch should prevent apply.
    proposal = _proposal_with_baseline("BASELINE_DIFFERENT")
    out = evaluate_proposal_constitutional(proposal, deps=deps)

    assert out.result.value == "MISMATCH"
    assert calls == ["current_hash", "noop", "duplicate"]
