from dataclasses import dataclass

@dataclass(frozen=True)
class LearningCanonConfig:
    # Canon knobs (explicit; versioned by semantics, not values)
    window_mode: str            # "time" | "events"
    t_window: str               # e.g. "7d" (used when time mode)
    n_events_window: int        # used when events mode

    n_min: int
    k_confirmations: int
    epsilon_max: float

    # Rate limiting
    period: str                 # e.g. "7d"
    limit_x: int                # max proposals per period
    cooldown: str               # e.g. "7d"
    rest_period: str            # e.g. "7d"
