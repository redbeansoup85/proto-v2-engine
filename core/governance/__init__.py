"""
Governance package (Contract-First).

Bound to:
- L4 Constitution: Section AQ (Approval Queue) — LOCKED
- L3 Operational Canon: Learning → Policy Cycle v1.0 — LOCKED
- L3 Operational Pack: Learning→Policy Governance v1.0 — LOCKED

No silent changes: any contract change requires a version bump.
"""
from .governance_version import OP_CANON_VERSION, OP_PACK_VERSION, REQUIRED_CONSTITUTION_SECTIONS
from .proposal_schema import PolicyProposal
from .proposal_validator import validate_proposal_prequeue
from .human_gate import evaluate_human_gate
from .queue_outcomes import QueueOutcome, QueueResult
from .queue_evaluator import QueueDeps, evaluate_proposal_constitutional

__all__ = [
    "OP_CANON_VERSION",
    "OP_PACK_VERSION",
    "REQUIRED_CONSTITUTION_SECTIONS",
    "PolicyProposal",
    "validate_proposal_prequeue",
    "evaluate_human_gate",
    "QueueOutcome",
    "QueueResult",
]
