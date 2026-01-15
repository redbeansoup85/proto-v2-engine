# proto-v2-engine/engine/recommendations_v0_1.py
from __future__ import annotations

from typing import List, Dict, Any

from core.contracts import EngineDecision, DecisionMode, Severity

def make_recommendations_v0_1(decision: EngineDecision) -> List[Dict[str, Any]]:
    """
    v0.1: 실행 시스템(C) 없이도 쓸 수 있는 '가이드' 형태 권고.
    """
    recs: List[Dict[str, Any]] = []

    if decision.mode == DecisionMode.SUPPRESS:
        recs.append({"type": "alert", "level": "critical", "message": "Immediate staff attention recommended."})
        recs.append({"type": "action", "message": "Reduce stimulation: lower noise/light, provide calming intervention."})
        return recs

    if decision.severity in (Severity.HIGH, Severity.CRITICAL):
        recs.append({"type": "alert", "level": "high", "message": "High-risk pattern detected. Monitor closely."})

    if decision.mode == DecisionMode.OBSERVE_MORE:
        recs.append({"type": "observe", "message": "Collect more data for next window; avoid strong interventions unless risk escalates."})
    else:
        recs.append({"type": "allow", "message": "Proceed; continue monitoring with standard cadence."})

    return recs
