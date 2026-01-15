from __future__ import annotations

import pytest

from core.judgment import (
    DpaOption,
    InMemoryDpaRepository,
    SimpleStaticComposer,
    DpaService,
    HumanDecision,
    DecisionStatus,
    PolicyError,
)


def test_service_create_get_approve_apply():
    repo = InMemoryDpaRepository()
    composer = SimpleStaticComposer(
        options=[DpaOption(option_id="opt_ok", title="OK")],
        constraints={"l4": ["NO_AUTO_AUTHORIZE"]},
        system_position={"confidence": 0.5},
    )
    svc = DpaService(repo=repo, composer=composer)

    dpa = svc.create_dpa(event_id="evt_1", context={"event": {"id": "evt_1"}}, dpa_id="dpa_1")
    assert dpa.status == DecisionStatus.DPA_CREATED

    dpa2 = svc.get_dpa(dpa_id="dpa_1")
    assert dpa2.event_id == "evt_1"

    decision = HumanDecision(
        selected_option_id="opt_ok",
        reason_codes=["SAFE"],
        reason_note="ok",
        approver_name="Alice",
        approver_role="Supervisor",
        signature="Alice@2026-01-10T00:00:00Z",
    )
    dpa3 = svc.submit_human_decision(dpa_id="dpa_1", decision=decision)
    assert dpa3.status == DecisionStatus.APPROVED

    dpa4 = svc.apply(dpa_id="dpa_1")
    assert dpa4.status == DecisionStatus.APPLIED


def test_service_not_found_is_409():
    repo = InMemoryDpaRepository()
    composer = SimpleStaticComposer(options=[DpaOption(option_id="opt_ok", title="OK")])
    svc = DpaService(repo=repo, composer=composer)

    with pytest.raises(PolicyError) as e:
        svc.get_dpa(dpa_id="missing")

    err = e.value
    assert err.http_status == 409
    assert err.code == "DPA_NOT_FOUND"
