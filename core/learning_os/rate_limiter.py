from dataclasses import dataclass
from typing import Dict
import time

@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    reason: str

class RateLimiter:
    """
    Simple deterministic limiter:
    - limit_x emissions per period_seconds
    - cooldown/rest are represented as additional blocks (v1: not fully time-parsed)
    """
    def __init__(self, period_seconds: int, limit_x: int):
        self.period_seconds = period_seconds
        self.limit_x = limit_x
        self._events: Dict[str, list] = {}  # key -> list of timestamps

    def check_and_record(self, key: str, now: float) -> RateLimitDecision:
        ts = self._events.setdefault(key, [])
        # prune
        cutoff = now - self.period_seconds
        ts[:] = [t for t in ts if t >= cutoff]

        if len(ts) >= self.limit_x:
            return RateLimitDecision(False, "RATE_LIMIT_EXCEEDED")

        ts.append(now)
        return RateLimitDecision(True, "OK")
