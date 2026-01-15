from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from .queue_outcomes import QueueOutcome, QueueResult
from .proposal_schema import PolicyProposal


@dataclass(frozen=True)
class QueueDeps:
    """
    Adapter dependencies.

    Existing queue functions are injected here.
    This evaluator enforces constitutional order and returns a stable QueueOutcome.
    """
    get_current_policy_hash: Callable[[], str]
    has_policy_hash_been_applied: Callable[[str], bool]
    apply_patch: Callable[[PolicyProposal], Tuple[bool, str, Optional[str], str]]
    is_noop: Callable[[PolicyProposal], bool]


def evaluate_proposal_constitutional(
    proposal: PolicyProposal,
    *,
    deps: QueueDeps,
) -> QueueOutcome:
    """
    Constitutional evaluation order (LOCKED by L4 AQ):

    1) noop
    2) duplicate
    3) mismatch
    4) apply or skip
    """
    policy_hash_before = deps.get_current_policy_hash()
    baseline = proposal.baseline.policy_hash

    # 1) NOOP
    if deps.is_noop(proposal):
        return QueueOutcome(
            proposal_id=proposal.proposal_id,
            baseline_policy_hash=baseline,
            result=QueueResult.NOOP,
            reason_code="NOOP_DIFF_EMPTY",
            policy_hash_before=policy_hash_before,
            policy_hash_after=policy_hash_before,
            applied_patch_id=None,
        )

    # 2) DUPLICATE
    if deps.has_policy_hash_been_applied(baseline):
        return QueueOutcome(
            proposal_id=proposal.proposal_id,
            baseline_policy_hash=baseline,
            result=QueueResult.DUPLICATE,
            reason_code="DUPLICATE_BASELINE_ALREADY_APPLIED",
            policy_hash_before=policy_hash_before,
            policy_hash_after=policy_hash_before,
            applied_patch_id=None,
        )

    # 3) MISMATCH
    if baseline != policy_hash_before:
        return QueueOutcome(
            proposal_id=proposal.proposal_id,
            baseline_policy_hash=baseline,
            result=QueueResult.MISMATCH,
            reason_code="MISMATCH_BASELINE_VS_CURRENT",
            policy_hash_before=policy_hash_before,
            policy_hash_after=policy_hash_before,
            applied_patch_id=None,
        )

    # 4) APPLY or SKIP
    applied, policy_hash_after, applied_patch_id, reason_code = deps.apply_patch(proposal)

    return QueueOutcome(
        proposal_id=proposal.proposal_id,
        baseline_policy_hash=baseline,
        result=QueueResult.APPLIED if applied else QueueResult.SKIPPED,
        reason_code=reason_code or ("APPLIED" if applied else "SKIPPED"),
        policy_hash_before=policy_hash_before,
        policy_hash_after=policy_hash_after if policy_hash_after else policy_hash_before,
        applied_patch_id=applied_patch_id,
    )
