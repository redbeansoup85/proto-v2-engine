from __future__ import annotations

import pytest

from core.judgment import (
    DpaOption,
    DpaRecord,
    HumanDecision,
    PolicyError,
    DecisionStatus,
    apply,
    submit_human_decision,
)


def _sample_dpa() -> DpaRecord:
    return DpaRecord(
        dpa_id="dpa_001",
        event_id="evt_001",
        context_json={"k": "v"},
        options_json=[
            DpaOption(option_id="opt_ok", title="OK", blocked=False),
            DpaOption(option_id="opt_blocked", title="NO", blocked=True, blocked_reason="L4 constraint"),
        ],
        constraints_json={"l4": ["NO_AUTOMATION_AUTH"]},
        system_position_json={"confidence": 0.51},
    )


def test_blocked_option_conflict():
    dpa = _sample_dpa()
    decision = HumanDecision(
        selected_option_id="opt_blocked",
        reason_codes=["TEST"],
        reason_note="try blocked",
        approver_name="Alice",
        approver_role="Supervisor",
        signature="Alice@2026-01-10T00:00:00Z",
    )

    with pytest.raises(PolicyError) as e:
        submit_human_decision(dpa, decision)

    err = e.value
    assert err.http_status == 409
    assert err.code == "OPTION_BLOCKED"


def test_happy_path_approve_then_apply():
    dpa = _sample_dpa()
    decision = HumanDecision(
        selected_option_id="opt_ok",
        reason_codes=["SAFE"],
        reason_note="ok",
        approver_name="Alice",
        approver_role="Supervisor",
        signature="Alice@2026-01-10T00:00:00Z",
    )

    dpa = submit_human_decision(dpa, decision)
    assert dpa.status == DecisionStatus.APPROVED
    assert dpa.human_decision_json is not None
    assert dpa.approved_at is not None
    assert dpa.approved_by is not None

    dpa = apply(dpa)
    assert dpa.status == DecisionStatus.APPLIED
