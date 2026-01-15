from dataclasses import dataclass
from typing import List
from .observation_store import Observation

@dataclass(frozen=True)
class SampleCheck:
    ok: bool
    n_min: int
    n_observed: int
    reason: str

def check_sample_sufficiency(observations: List[Observation], *, n_min: int) -> SampleCheck:
    n = len(observations)
    if n < n_min:
        return SampleCheck(ok=False, n_min=n_min, n_observed=n, reason="INSUFFICIENT_SAMPLES")
    return SampleCheck(ok=True, n_min=n_min, n_observed=n, reason="OK")
