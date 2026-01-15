from typing import List
from .observation_store import Observation

def select_window(observations: List[Observation], *, mode: str, n_events: int) -> List[Observation]:
    """
    v1 windowing: event-based selection only (deterministic and testable).
    time-based windowing can be added later with explicit parsing rules.
    """
    if mode not in {"events", "time"}:
        raise ValueError("mode must be 'events' or 'time'")
    if mode == "events":
        if n_events <= 0:
            raise ValueError("n_events must be > 0")
        return observations[-n_events:]
    # time mode placeholder: caller must provide already-filtered observations or implement time parsing.
    return observations
