from __future__ import annotations

from typing import Any, List

from adapters.prelude_adapter import (

    adapt_prelude_output_to_engine_input,
    make_minimal_engine_output,
)

from core.contracts import EngineDecision, EngineOutput, EngineSignal, SignalType, Severity
from core.emotion_os.emit_signals import emit_emotion_signals

# scene_state builders
from core.multi_reality_os.emit_scene_state import build_scene_state_v0_1, build_scene_state_v0_2

# policy (v0.2/v0.3)
from core.engine.recommendations_v0_1 import make_recommendations_v0_1
from core.policy.policy_v0_2 import compute_policy_v0_2
from core.policy.policy_v0_3 import compute_policy_v0_3

# policy memory (process-wide, smoke/local)
from core.policy.memory.in_memory import InMemoryPolicyMemory
from core.policy.memory.ports import PolicyMemoryKey

_POLICY_MEMORY = InMemoryPolicyMemory()

_SEVERITY_RANK = {
    Severity.LOW: 0,
    Severity.MEDIUM: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}

def _max_severity(a: Severity, b: Severity) -> Severity:
    return a if _SEVERITY_RANK[a] >= _SEVERITY_RANK[b] else b

import inspect

def _call_policy(fn, **candidates):
    """정확한 인자명이 뭐든 간에, signature에 있는 키만 골라 호출"""
    params = inspect.signature(fn).parameters
    kwargs = {k: v for k, v in candidates.items() if k in params}
    return fn(**kwargs)

def run_engine(prelude_output: Any, *, strict: bool = True) -> EngineOutput:
    # 1) Adapter: prelude output -> EngineInput
    inp = adapt_prelude_output_to_engine_input(prelude_output, strict=strict)
    # 2) Minimal base output (prelude 기반)
    base = make_minimal_engine_output(inp)
    # 3) emotion_os signals
    emotion_signals: List[EngineSignal] = emit_emotion_signals(inp)
    # 4) signals 결합 (frozen 대응: 새 리스트)
    merged_signals: List[EngineSignal] = list(base.signals) + emotion_signals
    # 5) (기존 bump 로직 유지) emotion high-risk 신호가 있으면 severity 상향
    bump = any(
        (s.type == SignalType.EMOTION) and (s.severity in (Severity.HIGH, Severity.CRITICAL))
        for s in emotion_signals
    )
    new_decision = base.decision
    if bump:
        new_decision = EngineDecision(
            mode=base.decision.mode,  # v0.1: mode는 아직 prelude 기반 유지
            severity=_max_severity(base.decision.severity, Severity.HIGH),
            rationale=base.decision.rationale + ["emotion_os detected high-risk pattern"],
        )
    # 6) ✅ v0.1 policy가 최종 결정을 한다 (override 가능)
    # 7) ✅ recommendations 생성
    # 8) ✅ scene_state v0.1 생성 (UI/Orchestrator에 바로 쓸 요약 상태)
    scene_state = build_scene_state_v0_2(inp, merged_signals)
    # --- Policy v0.3 with Memory (load → apply → save) ---
    mem_key = PolicyMemoryKey(
        org_id=inp.meta.org_id,
        site_id=inp.meta.site_id,
        channel=inp.meta.channel or "unknown",
    )
    prev_state = _POLICY_MEMORY.load_last_scene_state(mem_key)
    pol3 = compute_policy_v0_3(
        channel=inp.meta.channel,
        current_decision=new_decision,
        signals=merged_signals,
        prev_scene_state=prev_state,
        now_ts_iso=inp.meta.ts_end_iso,
    )
    # decision update (if changed)
    new_decision = pol3.decision
    # temporal merge
    try:
        scene_state["temporal"] = {
            **(scene_state.get("temporal") or {}),
            **(pol3.temporal_patch or {}),
        }
    except Exception:
        pass
    # save for next window
    _POLICY_MEMORY.save_scene_state(mem_key, scene_state)
    # --- Policy v0.2 (PURE) : accumulation / cooldown scaffold ---
    # prev_scene_state는 아직 메모리 레이어가 없으므로 None (smoke에서는 temporal이 초기값으로 시작)
    pol2 = compute_policy_v0_2(
        channel=inp.meta.channel,
        current_decision=new_decision,
        signals=merged_signals,
        prev_scene_state=None,
        now_ts_iso=inp.meta.ts_end_iso,
    )
    # decision severity bump (if any)
    new_decision = pol2.decision
    # scene_state.temporal patch (merge)
    try:
        scene_state["temporal"] = {
            **(scene_state.get("temporal") or {}),
            **(pol2.temporal_patch or {}),
        }
    except Exception:
        # fail-safe: never break engine for temporal enrichment
        pass
    # 9) EngineOutput 재구성 (frozen 대응)
        # --- safety: ensure final_decision is always defined ---
    try:
        final_decision  # type: ignore[name-defined]
    except NameError:
        final_decision = locals().get("decision_v0_2") or locals().get("new_decision") or base.decision

        # --- safety: ensure recs is always defined ---
    try:
        recs  # type: ignore[name-defined]
    except NameError:
        recs = base.recommendations

        # --- ensure recommendations are generated from final_decision ---
    recs = make_recommendations_v0_1(final_decision)

    return EngineOutput(
        meta=base.meta,
        decision=final_decision,
        signals=merged_signals,
        scene_state=scene_state,      # ✅ base.scene_state → v0.1 scene_state로 교체
        recommendations=recs,
        debug=base.debug,
    )
