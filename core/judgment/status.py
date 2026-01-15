from __future__ import annotations

from enum import Enum


class DecisionStatus(str, Enum):
    EVENT_INGESTED = "EVENT_INGESTED"
    DPA_CREATED = "DPA_CREATED"
    HUMAN_REVIEWING = "HUMAN_REVIEWING"
    APPROVED = "APPROVED"
    APPLIED = "APPLIED"
    ABORTED = "ABORTED"
