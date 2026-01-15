from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from core.contracts.orchestrator import DeliveryRouting
from core.contracts.policy import PolicyDecision, Severity
from core.contracts.rationale_codes import RationaleCode
from core.contracts.scene import SceneContext, SceneRef, SceneStatus, SceneSummary


@dataclass
class SceneRuntimeState:
    """Not persisted to L2 (operational only)."""
    low_streak: int = 0
    peak_severity: Severity = Severity.low
    total_decisions: int = 0
    rationale_counter: Dict[str, int] = None

    def __post_init__(self):
        if self.rationale_counter is None:
            self.rationale_counter = {}


def _severity_rank(s: Severity) -> int:
    return {"low": 0, "medium": 1, "high": 2, "critical": 3}[s.value]


def should_close(scene_state: SceneRuntimeState) -> bool:
    return scene_state.low_streak >= 3 and scene_state.total_decisions >= 3


def update_runtime_state(
    st: SceneRuntimeState,
    decision: PolicyDecision,
    rationale_codes: List[str],
) -> SceneRuntimeState:
    st.total_decisions += 1

    # peak severity
    if _severity_rank(decision.severity) > _severity_rank(st.peak_severity):
        st.peak_severity = decision.severity

    # low streak for closing
    if decision.severity == Severity.low:
        st.low_streak += 1
    else:
        st.low_streak = 0

    for rc in rationale_codes:
        st.rationale_counter[rc] = st.rationale_counter.get(rc, 0) + 1

    return st


def build_scene_summary(
    *,
    scene: SceneRef,
    st: SceneRuntimeState,
    ts_end: str,
    delivery_types: Tuple[str, ...],
    human_interventions: Tuple[str, ...] = (),
    top_k: int = 5,
) -> SceneSummary:
    # top rationale codes by count
    items = sorted(st.rationale_counter.items(), key=lambda x: x[1], reverse=True)[:top_k]
    top_codes = tuple(RationaleCode(k) if k in RationaleCode.__members__.values() else k for k, _ in items)  # best-effort
    # If above is messy due to enum, store strings in v0.1
    top_codes_str = tuple(k for k, _ in items)

    return SceneSummary(
        scene_id=scene.scene_id,
        context=scene.context,
        ts_start=scene.ts_start,
        ts_end=ts_end,
        peak_severity=st.peak_severity,
        total_decisions=st.total_decisions,
        key_rationale_codes=tuple(),  # keep empty typed; store strings in L2 JSONL via adapter later
        delivery_types=delivery_types,
        human_interventions=human_interventions,
        outcome_label=None,
    ), top_codes_str
