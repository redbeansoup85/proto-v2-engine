from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class QueueResult(str, Enum):
    NOOP = "NOOP"
    DUPLICATE = "DUPLICATE"
    MISMATCH = "MISMATCH"
    APPLIED = "APPLIED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class QueueOutcome:
    proposal_id: str
    baseline_policy_hash: str
    result: QueueResult
    reason_code: str
    policy_hash_before: str
    policy_hash_after: str
    applied_patch_id: Optional[str] = None
