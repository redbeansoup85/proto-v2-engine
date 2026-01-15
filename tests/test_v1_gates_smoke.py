from core.contracts.orchestrator import (
    ResponsibilityAcceptance,
    ResponsibilityDecision,
    ExecutionAuthorizationRequest,
    ExecutionScope,
    ExecutionLimit,
    ExecutionTimebox,
    assert_responsibility_accepted,
    assert_execution_request_valid,
)

def test_gate1_requires_accept():
    r = ResponsibilityAcceptance(
        decision=ResponsibilityDecision.REJECT,
        actor_id="user_001",
        actor_role="owner",
        ts="2026-01-06T15:30:00+11:00",
        judgment_ref="judgment:abc123",
    )
    try:
        assert_responsibility_accepted(r)
        assert False, "expected AssertionError"
    except AssertionError:
        pass

def test_gate2_requires_valid_request():
    r = ResponsibilityAcceptance(
        decision=ResponsibilityDecision.ACCEPT,
        actor_id="user_001",
        actor_role="owner",
        ts="2026-01-06T15:30:00+11:00",
        judgment_ref="judgment:abc123",
    )
    req = ExecutionAuthorizationRequest(
        responsibility=r,
        scope=ExecutionScope(domain="family", permitted_actions=("ORDER_CREATE",), assets=("BTC",)),
        limit=ExecutionLimit(max_notional_usd=1000, max_order_count=1),
        timebox=ExecutionTimebox(valid_from="2026-01-06T15:30:00+11:00", valid_until="2026-01-06T16:00:00+11:00"),
        judgment_ref="judgment:abc123",
        request_payload={"action": "ORDER_CREATE", "symbol": "BTCUSDT", "side": "BUY"},
    )
    assert_execution_request_valid(req)

def test_gate2_rejects_autorun():
    r = ResponsibilityAcceptance(
        decision=ResponsibilityDecision.ACCEPT,
        actor_id="user_001",
        actor_role="owner",
        ts="2026-01-06T15:30:00+11:00",
        judgment_ref="judgment:abc123",
    )
    # Force an invalid object
    req = ExecutionAuthorizationRequest(
        auto_action=True,  # should fail invariant
        responsibility=r,
        scope=ExecutionScope(domain="family"),
        limit=ExecutionLimit(),
        timebox=ExecutionTimebox(valid_from="2026-01-06T15:30:00+11:00", valid_until="2026-01-06T16:00:00+11:00"),
        judgment_ref="judgment:abc123",
    )
    try:
        assert_execution_request_valid(req)
        assert False, "expected AssertionError"
    except AssertionError:
        pass
