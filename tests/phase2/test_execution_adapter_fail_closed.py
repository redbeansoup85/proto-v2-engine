from core.execution_adapter import (
    ApprovalArtifact,
    ExecutionBlocked,
    ExecutionEnvelope,
    NoopExecutionAdapter,
)

CAPS_OK = {
    "allowed_scopes": ["automation"],
    "allowed_actions": ["PLACE_ORDER", "CANCEL_ORDER"],
    "allowed_venues": ["BINANCE"],
}

def _env():
    return ExecutionEnvelope(
        execution_scope="automation",
        allowed_actions=["PLACE_ORDER"],
        allowed_venues=["BINANCE"],
        max_size="100",
        time_limit_utc="2026-01-22T00:10:00Z",
        idempotency_key="test-001",
        risk_flags=[],
    )

def _approval_ok():
    return ApprovalArtifact(
        approval_id="appr-1",
        decision="APPROVE",
        approver_id="human-1",
        expires_at_utc="2099-01-01T00:00:00Z",
        policy_refs=["POL-1"],
    )

def test_deny_without_evidence():
    ad = NoopExecutionAdapter()
    try:
        ad.execute(_env(), _approval_ok(), [], CAPS_OK)
        assert False, "expected ExecutionBlocked"
    except ExecutionBlocked as e:
        assert "evidence" in str(e)

def test_deny_on_expired_approval():
    ad = NoopExecutionAdapter()
    appr = ApprovalArtifact(
        approval_id="appr-1",
        decision="APPROVE",
        approver_id="human-1",
        expires_at_utc="2000-01-01T00:00:00Z",
        policy_refs=["POL-1"],
    )
    try:
        ad.execute(_env(), appr, ["e1"], CAPS_OK)
        assert False, "expected ExecutionBlocked"
    except ExecutionBlocked as e:
        assert "expired" in str(e)

def test_deny_on_missing_capability():
    ad = NoopExecutionAdapter()
    bad_caps = {"allowed_scopes": ["manual"], "allowed_actions": ["PLACE_ORDER"], "allowed_venues": ["BINANCE"]}
    try:
        ad.execute(_env(), _approval_ok(), ["e1"], bad_caps)
        assert False, "expected ExecutionBlocked"
    except ExecutionBlocked as e:
        assert "execution_scope" in str(e)

def test_noop_adapter_blocks_even_when_valid():
    ad = NoopExecutionAdapter()
    res = ad.execute(_env(), _approval_ok(), ["e1"], CAPS_OK)
    assert res.status == "BLOCKED"
