from __future__ import annotations

from dataclasses import dataclass
from core.contracts._compat import StrEnum
from typing import Optional


class FeedbackLabel(StrEnum):
    TP = "TP"
    FP = "FP"
    TN = "TN"
    FN = "FN"
    UNCLEAR = "UNCLEAR"


@dataclass(frozen=True)
class FeedbackRecord:
    case_id: str
    label: FeedbackLabel
    labeler_role: str
    label_ts: str  # ISO8601 string
    notes: Optional[str] = None
