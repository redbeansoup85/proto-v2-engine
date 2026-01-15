from dataclasses import dataclass
from typing import List
from .observation_store import Observation

@dataclass(frozen=True)
class StabilityResult:
    ok: bool
    k_confirmations: int
    epsilon: float
    disagreement_rate: float
    summary: str

def check_stability_v1(observations: List[Observation], *, k_confirmations: int, epsilon_max: float) -> StabilityResult:
    """
    Conservative, testable stability v1:
    - Consider last K directions
    - Require all K to be identical and not 'neutral'
    - Disagreement rate across window must be <= epsilon_max
    """
    if k_confirmations <= 0:
        raise ValueError("k_confirmations must be > 0")
    if not observations:
        return StabilityResult(False, k_confirmations, epsilon_max, 1.0, "no observations")

    # Window disagreement rate
    dirs = [o.direction for o in observations if o.direction]
    if not dirs:
        return StabilityResult(False, k_confirmations, epsilon_max, 1.0, "no valid direction signals")

    majority = max(set(dirs), key=dirs.count)
    disagreement = sum(1 for d in dirs if d != majority)
    disagreement_rate = disagreement / max(1, len(dirs))

    # K-confirmations on tail
    tail = dirs[-k_confirmations:] if len(dirs) >= k_confirmations else []
    k_ok = len(tail) == k_confirmations and all(d == tail[0] for d in tail) and tail[0] != "neutral"

    ok = k_ok and (disagreement_rate <= epsilon_max)
    summary = f"majority={majority}, tail={tail[-1] if tail else 'n/a'}, disagreement_rate={disagreement_rate:.3f}"
    return StabilityResult(ok, k_confirmations, epsilon_max, disagreement_rate, summary)
