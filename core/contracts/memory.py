from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence, Tuple

from core.contracts.policy import Channel, PolicyDecision


@dataclass(frozen=True)
class PolicyMemorySnapshot:
    channel: Channel
    accumulation_score: float
    strike_count: int
    cooldown_until_ts: Optional[str]  # ISO8601
    human_review_required: bool
    last_decision: Optional[PolicyDecision] = None
    last_critical_ts: Optional[str] = None


@dataclass(frozen=True)
class DecisionRecord:
    window_id: str
    ts_start: str
    ts_end: str
    channel: Channel
    decision: PolicyDecision
    key_signals: Tuple[dict, ...] = ()  # {name,severity,confidence} etc.
    recommendations_digest: Tuple[str, ...] = ()  # types/codes


class PolicyMemoryPort(Protocol):
    def get_state(self, channel: Channel) -> PolicyMemorySnapshot: ...
    def get_last_decision(self, channel: Channel) -> Optional[DecisionRecord]: ...
    def get_history(self, channel: Channel, limit: int = 50, since_ts: Optional[str] = None) -> Sequence[DecisionRecord]: ...

    def append_decision(self, channel: Channel, record: DecisionRecord) -> None: ...
    def update_accumulator(self, channel: Channel, delta: float, reason_code: str) -> PolicyMemorySnapshot: ...
    def set_cooldown(self, channel: Channel, until_ts: str, reason_code: str) -> PolicyMemorySnapshot: ...

    def apply_decay(self, channel: Channel, now_ts: str) -> PolicyMemorySnapshot: ...
    def soft_reset(self, channel: Channel, reason_code: str) -> PolicyMemorySnapshot: ...
    def hard_reset(self, channel: Channel, reason_code: str) -> PolicyMemorySnapshot: ...

    def set_human_override(
        self,
        channel: Channel,
        state: str,
        actor: str,
        expires_ts: str,
        note: Optional[str] = None,
    ) -> PolicyMemorySnapshot: ...
