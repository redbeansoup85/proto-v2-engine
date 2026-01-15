from __future__ import annotations

from dataclasses import dataclass
from core.contracts._compat import StrEnum
from typing import Tuple

from core.contracts.rationale_codes import RationaleCode


class Channel(StrEnum):
    childcare = "childcare"
    fnb = "fnb"
    trading = "trading"


class DecisionMode(StrEnum):
    observe_more = "observe_more"
    suppress = "suppress"


class Severity(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


@dataclass(frozen=True)
class PolicyDecision:
    mode: DecisionMode
    severity: Severity
    rationale_codes: Tuple[RationaleCode, ...]
