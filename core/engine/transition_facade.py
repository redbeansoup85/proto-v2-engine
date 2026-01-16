from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict
import inspect

from core.engine.constitutional_transition import constitutional_transition
from core.judgment.ports import ApprovalQueuePort, DpaApplyPort
from core.judgment.persistence.noop_apply_port import NoopDpaApplyPort


@dataclass(frozen=True)
class TransitionDeps:
    """
    v0.8 boundary:
    - Router owns ApprovalQueue usage.
    - Engine sees JudgmentPort + Prelude output only.
    - Apply is always behind port (default fail-closed).
    """
    approval_queue: ApprovalQueuePort
    judgment_port: Any  # structural: must have get_approval(dpa_id=...)
    dpa_apply_port: DpaApplyPort = NoopDpaApplyPort()


def run_transition(
    *,
    deps: TransitionDeps,
    dpa_id: str,
    prelude_output: Any,
) -> Any:
    candidate_kwargs: Dict[str, Any] = {
        "dpa_id": dpa_id,
        "judgment_port": deps.judgment_port,
        "prelude_output": prelude_output,
        "dpa_apply_port": deps.dpa_apply_port,
        "strict": True,
        "emotion_port": None,
    }

    sig = inspect.signature(constitutional_transition)
    safe_kwargs = {k: v for k, v in candidate_kwargs.items() if k in sig.parameters}
    return constitutional_transition(**safe_kwargs)
