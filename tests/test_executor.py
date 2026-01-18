from datetime import datetime, timedelta, timezone

import pytest

from core.contracts.execution_envelope import ExecutionEnvelope
from core.execution.executor import run_execution, ExecutionContext
from core.contracts.actions import ExecutionAction
from core.contracts.errors import ContractConstraintError, ContractMalformedError


class _Port:
    def __init__(self):
        self.called = False

    def apply(self, dpa_id: str, selected_option_id: str, context=None):
        self.called = True
        return {"ok": True, "dpa_id": dpa_id, "selected_option_id": selected_option_id}


def _env_apply():
    now = datetime.now(timezone.utc)
    payload = {
        "meta": {
            "contract_id": "01JEXECENV_TEST_0002",
            "envelope_id": "env-test-0002",
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=60)).isoformat(),
            "issuer": "tests",
            "version": "1.0.0",
        },
        "authority": {
            "domain": "demo",
            "allowed_actions": ["apply"],
            "forbidden_actions": [],
            "confidence_floor": 0.0,
        },
        "constraints": {
            "latency_budget_ms": 1000,
            "resource_ceiling": {"cpu_pct": 90.0, "mem_mb": 1024},
            "data_scope": {"allowed_sources": ["judgment:approval_queue"], "forbidden_sources": []},
        },
        "audit": {"trace_level": "standard", "retention_policy": "append_only"},
        "human_approval": {"approver_id": "human_001", "approval_ref": "APPROVAL-REF-TEST-002"},
    }
    return ExecutionEnvelope.model_validate(payload)


def test_executor_fail_closed_on_missing_sources():
    env = _env_apply()
    port = _Port()
    with pytest.raises(ContractConstraintError):
        run_execution(
            envelope=env,
            port=port,
            ctx=ExecutionContext(
                action=ExecutionAction.apply,
                confidence=1.0,
                input_sources=[],
                dpa_id="dpa_001",
                selected_option_id="opt_approve",
                context=None,
            ),
        )


def test_executor_fail_closed_on_invalid_confidence():
    env = _env_apply()
    port = _Port()
    with pytest.raises(ContractMalformedError):
        run_execution(
            envelope=env,
            port=port,
            ctx=ExecutionContext(
                action=ExecutionAction.apply,
                confidence=2.0,
                input_sources=["judgment:approval_queue"],
                dpa_id="dpa_001",
                selected_option_id="opt_approve",
                context=None,
            ),
        )
