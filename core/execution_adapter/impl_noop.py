from __future__ import annotations

from typing import Any, Dict, List, Set

from .contract import (
    ApprovalArtifact,
    ExecutionBlocked,
    ExecutionEnvelope,
    ExecutionResultBlocked,
)


def _as_set(x) -> Set[str]:
    if not x:
        return set()
    return set([str(v) for v in x])


class NoopExecutionAdapter:
    """
    Phase-2: default fail-closed.
    - Invalid cases: raise ExecutionBlocked (catchable)
    - Valid case: return ExecutionResultBlocked(status="BLOCKED", reason_code="NOOP_BLOCKED", ...)
    """

    def execute(
        self,
        env: ExecutionEnvelope,
        approval: ApprovalArtifact,
        evidence_event_ids: List[str],
        capabilities: Dict[str, Any],
    ):
        # 1) evidence required
        if not evidence_event_ids:
            raise ExecutionBlocked("NO_EVIDENCE", "missing evidence: evidence_event_ids is empty")

        # 2) approval expiry
        if approval.is_expired():
            raise ExecutionBlocked("APPROVAL_EXPIRED", "approval expired")

        # 3) capability gate
        allowed_scopes = _as_set(capabilities.get("allowed_scopes"))
        cap_actions = _as_set(capabilities.get("allowed_actions"))
        cap_venues = _as_set(capabilities.get("allowed_venues"))

        if env.execution_scope not in allowed_scopes:
            raise ExecutionBlocked("CAPABILITY_MISSING", "execution_scope not allowed")

        env_actions = _as_set(env.allowed_actions)
        env_venues = _as_set(env.allowed_venues)

        if not env_actions:
            raise ExecutionBlocked("NO_ACTION", "missing allowed_actions")
        if not env_venues:
            raise ExecutionBlocked("NO_VENUE", "missing allowed_venues")

        if env_actions.isdisjoint(cap_actions):
            raise ExecutionBlocked("CAPABILITY_MISSING", "allowed_actions not permitted")
        if env_venues.isdisjoint(cap_venues):
            raise ExecutionBlocked("CAPABILITY_MISSING", "allowed_venues not permitted")

        # 4) NOOP policy: valid but still blocks (return object, not exception)
        return ExecutionResultBlocked(
            status="BLOCKED",
            reason_code="NOOP_BLOCKED",
            reason_detail="noop adapter: execution disabled in Phase-2",
        )
