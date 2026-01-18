from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Dict, Tuple


@dataclass(frozen=True)
class ReplayKey:
    approval_id: str
    envelope_id: str


class IdempotencyGuard:
    """
    Minimal in-memory idempotency guard.

    Policy:
    - First use of (approval_id, envelope_id) => allow
    - Second use => replay detected => deny
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._seen: Dict[ReplayKey, int] = {}

    def check_and_mark(self, approval_id: str, envelope_id: str) -> Tuple[bool, int]:
        """
        Returns: (is_first_use, count_after_mark)
        - is_first_use=True => first time seen (allow)
        - is_first_use=False => replay (deny)
        """
        key = ReplayKey(approval_id=approval_id, envelope_id=envelope_id)
        with self._lock:
            cnt = self._seen.get(key, 0) + 1
            self._seen[key] = cnt
            return (cnt == 1), cnt
