# proto-v2-engine/multi_reality_os/models/reality_link.py

from dataclasses import dataclass


@dataclass
class RealityLink:
    from_pl: str
    to_pl: str

    conflict_level: float  # 0~1
    benefit_alignment: float  # 0~1
