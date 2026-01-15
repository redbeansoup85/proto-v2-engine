"""
Learning OS (Proposal Producer)

Bound by:
- L3 Operational Canon — Learning → Policy Cycle v1.0 (LOCKED)
- L3 Operational Pack — Learning→Policy Governance v1.0 (LOCKED)
- L4 Constitution — Section AQ (Approval Queue) (LOCKED)

Learning may run continuously, but proposal emission is conditional and rate-limited.
"""
from .config import LearningCanonConfig
from .observation_store import ObservationStore, Observation
from .windowing import select_window
from .sampling import check_sample_sufficiency
from .stability import StabilityResult, check_stability_v1
from .evidence import EvidenceRef, EvidenceStore
from .rate_limiter import RateLimiter, RateLimitDecision
from .proposal_builder import build_policy_proposal

__all__ = [
    "LearningCanonConfig",
    "ObservationStore",
    "Observation",
    "select_window",
    "check_sample_sufficiency",
    "StabilityResult",
    "check_stability_v1",
    "EvidenceRef",
    "EvidenceStore",
    "RateLimiter",
    "RateLimitDecision",
    "build_policy_proposal",
]

from .proposal_emitter import emit_proposal_if_allowed, EmitDecision
from .queue_writer import QueueWriter
