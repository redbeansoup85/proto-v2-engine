from __future__ import annotations

from dataclasses import dataclass

from core.contracts import EngineOutput
from core.orchestrator.contracts import OrchestratorInput


@dataclass(frozen=True)
class EngineV01Adapter:
    """EngineOutput -> OrchestratorInput (read-only)"""

    def adapt(self, output: EngineOutput) -> OrchestratorInput:
        return OrchestratorInput(
            org_id=output.meta.org_id,
            site_id=output.meta.site_id,
            scene_id=output.meta.scene_id,
            channel=output.meta.channel,
            severity=output.decision.severity.value,
            decision_mode=output.decision.mode.value,
            scene_state=output.scene_state,
            recommendations=output.recommendations,
        )
