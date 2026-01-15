# proto-v2-engine/engine/policy_v0_1.py
from __future__ import annotations

from typing import List, Dict, Any, Optional

from core.contracts import (
    EngineInput,
    EngineDecision,
    EngineSignal,
    DecisionMode,
    Severity,
    SignalType,
)

_SEV_RANK = {
    Severity.LOW: 0,
    Severity.MEDIUM: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}

def _max_sev(a: Severity, b: Severity) -> Severity:
    return a if _SEV_RANK[a] >= _SEV_RANK[b] else b

def _max_signal_severity(signals: List[EngineSignal], *, sig_type: Optional[SignalType] = None) -> Optional[Severity]:
    picked = [s.severity for s in signals if (sig_type is None or s.type == sig_type)]
    if not picked:
        return None
    cur = picked[0]
    for s in picked[1:]:
        cur = _max_sev(cur, s)
    return cur

def apply_policy_v0_1(
    inp: EngineInput,
    base_decision: EngineDecision,
    signals: List[EngineSignal],
) -> EngineDecision:
    """
    v0.1 정책:
    - EMOTION이 CRITICAL이면 mode를 suppress로 강제
    - EMOTION이 HIGH 이상이면 severity를 최소 HIGH로 끌어올림
    - quality 낮으면 observe_more로 보수화 (단, CRITICAL emotion이면 suppress 우선)
    """
    decision = base_decision
    rationale = list(base_decision.rationale)

    emo_max = _max_signal_severity(signals, sig_type=SignalType.EMOTION)
    qual_sig = next((s for s in signals if s.type == SignalType.QUALITY and s.name == "quality_score"), None)
    uq_sig = next((s for s in signals if s.type == SignalType.UNCERTAINTY and s.name == "uncertainty_score"), None)

    quality_score = None
    if qual_sig is not None:
        try:
            quality_score = float(qual_sig.value)
        except Exception:
            quality_score = None

    uncertainty_score = None
    if uq_sig is not None:
        try:
            uncertainty_score = float(uq_sig.value)
        except Exception:
            uncertainty_score = None

    # 1) EMOTION CRITICAL → suppress (최우선)
    if emo_max == Severity.CRITICAL:
        decision = EngineDecision(
            mode=DecisionMode.SUPPRESS,
            severity=_max_sev(decision.severity, Severity.CRITICAL),
            rationale=rationale + ["policy_v0.1: CRITICAL emotion → suppress"],
        )
        return decision

    # 2) EMOTION HIGH → severity 최소 HIGH
    if emo_max == Severity.HIGH:
        decision = EngineDecision(
            mode=decision.mode,
            severity=_max_sev(decision.severity, Severity.HIGH),
            rationale=rationale + ["policy_v0.1: HIGH emotion → severity bump"],
        )

    # 3) 품질/불확실성 기반 보수화(관찰)
    # (예시 기준값: quality<0.6 or uncertainty>0.6 이면 observe_more)
    if (quality_score is not None and quality_score < 0.6) or (uncertainty_score is not None and uncertainty_score > 0.6):
        decision = EngineDecision(
            mode=DecisionMode.OBSERVE_MORE,
            severity=decision.severity,
            rationale=decision.rationale + ["policy_v0.1: low quality or high uncertainty → observe_more"],
        )

    return decision
