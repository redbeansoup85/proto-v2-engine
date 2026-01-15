from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from core.contracts import EngineSignal, Severity


# --- severity helpers ---------------------------------------------------------

_SEV_RANK: Dict[Optional[Severity], int] = {
    None: -1,
    Severity.LOW: 0,
    Severity.MEDIUM: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}


def _max_sev(a: Optional[Severity], b: Optional[Severity]) -> Optional[Severity]:
    return a if _SEV_RANK[a] >= _SEV_RANK[b] else b


def _max_signal_severity(signals: List[EngineSignal]) -> Optional[Severity]:
    cur: Optional[Severity] = None
    for s in signals:
        cur = _max_sev(cur, getattr(s, "severity", None))
    return cur


def _get_meta_field(inp: Any, name: str) -> Any:
    # 1) direct (legacy)
    v = getattr(inp, name, None)
    if v is not None:
        return v
    # 2) EngineInput.meta.*
    meta = getattr(inp, "meta", None)
    if meta is not None:
        return getattr(meta, name, None)
    return None


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _priority_from_severity(sev: str) -> str:
    s = (sev or "").lower()
    if s == "critical":
        return "urgent"
    if s == "high":
        return "high"
    if s == "medium":
        return "normal"
    return "low"


def _trend(last: str, cur: str) -> str:
    # last/cur are severity strings: low/medium/high/critical
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    a = order.get((last or "").lower(), 0)
    b = order.get((cur or "").lower(), 0)
    if b > a:
        return "rising"
    if b < a:
        return "falling"
    return "stable"


# --- v0.1 (existing) ----------------------------------------------------------

def build_scene_state_v0_1(inp: Any, signals: List[EngineSignal]) -> Dict[str, Any]:
    max_sev = _max_signal_severity(signals) or Severity.LOW

    # signals_by_type
    by_type: Dict[str, int] = {}
    for s in signals:
        t = getattr(getattr(s, "type", None), "value", None) or str(getattr(s, "type", "unknown"))
        by_type[t] = by_type.get(t, 0) + 1

    # emotion_flags (emotion 타입만 요약)
    emotion_flags: List[Dict[str, Any]] = []
    for s in signals:
        t = getattr(getattr(s, "type", None), "value", None) or ""
        if t == "emotion":
            emotion_flags.append(
                {
                    "name": s.name,
                    "severity": getattr(getattr(s, "severity", None), "value", None),
                    "confidence": s.confidence,
                }
            )

    return {
        "schema_version": "scene_state_v0.1",
        "window": {
            "ts_start_iso": _get_meta_field(inp, "ts_start_iso"),
            "ts_end_iso": _get_meta_field(inp, "ts_end_iso"),
            "channel": _get_meta_field(inp, "channel"),
        },
        "summary": {
            "max_severity": max_sev.value,
            "signals_total": len(signals),
            "signals_by_type": by_type,
        },
        "emotion_flags": emotion_flags,
    }


# --- v0.2 (new) ---------------------------------------------------------------

def build_scene_state_v0_2(
    inp: Any,
    signals: List[EngineSignal],
    *,
    prev_scene_state: Optional[Dict[str, Any]] = None,
    last_decision: Optional[Dict[str, Any]] = None,
    cooldown: Optional[Dict[str, Any]] = None,
    now_ts_iso: Optional[str] = None,
) -> Dict[str, Any]:
    """
    SceneState v0.2 생성기 (Temporal Intelligence)
    - prev_scene_state: 직전 스냅샷(있으면 trend/occurrences 계산에 사용)
    - last_decision: {"mode": "...", "severity": "...", "ts_iso": "..."} (optional)
    - cooldown: {"until_ts_iso": "...", "reason": "..."} (optional)
    - now_ts_iso: 없으면 meta.ts_end_iso -> utc now 순으로 채움
    """
    max_sev = _max_signal_severity(signals) or Severity.LOW

    # window
    ts_start = _get_meta_field(inp, "ts_start_iso")
    ts_end = _get_meta_field(inp, "ts_end_iso")
    ch = _get_meta_field(inp, "channel")

    # signals_by_type
    by_type: Dict[str, int] = {}
    for s in signals:
        t = getattr(getattr(s, "type", None), "value", None) or str(getattr(s, "type", "unknown"))
        by_type[t] = by_type.get(t, 0) + 1

    # emotion_flags
    emotion_flags: List[Dict[str, Any]] = []
    for s in signals:
        t = getattr(getattr(s, "type", None), "value", None) or ""
        if t == "emotion":
            emotion_flags.append(
                {
                    "name": s.name,
                    "severity": getattr(getattr(s, "severity", None), "value", None),
                    "confidence": s.confidence,
                }
            )

    current_severity = max_sev.value  # v0.4에서는 policy 결과와 결합 가능
    # temporal defaults
    prev_last = None
    prev_occ_10 = 0
    prev_occ_30 = 0

    if prev_scene_state:
        prev_temporal = prev_scene_state.get("temporal") or {}
        prev_last = prev_temporal.get("last_severity") or prev_scene_state.get("summary", {}).get("current_severity")
        prev_occ_10 = int(prev_temporal.get("occurrences_10m") or 0)
        prev_occ_30 = int(prev_temporal.get("occurrences_30m") or 0)

    # occurrences: 지금은 "위험 윈도우 발생"을 1로 취급하는 스켈레톤
    # v0.4에서 실제로는 timestamps/history를 통해 10m/30m 롤링 카운트로 확장
    is_risky = current_severity in ("high", "critical")
    occurrences_10m = prev_occ_10 + (1 if is_risky else 0)
    occurrences_30m = prev_occ_30 + (1 if is_risky else 0)

    last_severity = (prev_last or current_severity)
    severity_trend = _trend(last_severity, current_severity)

    # last_decision/cooldown: 없으면 최소 형태로 채움(옵션)
    now_ts_iso = now_ts_iso or ts_end or _iso_now()
    last_decision = last_decision or {
        "mode": None,
        "severity": None,
        "ts_iso": now_ts_iso,
    }
    cooldown = cooldown or {
        "until_ts_iso": None,
        "reason": None,
    }

    return {
        "schema_version": "scene_state_v0.2",
        "window": {
            "ts_start_iso": ts_start,
            "ts_end_iso": ts_end,
            "channel": ch,
        },
        "summary": {
            "current_severity": current_severity,
            "max_severity": current_severity,
            "signals_total": len(signals),
            "signals_by_type": by_type,
        },
        "emotion_flags": emotion_flags,
        "temporal": {
            "last_severity": last_severity,
            "severity_trend": severity_trend,
            "occurrences_10m": occurrences_10m,
            "occurrences_30m": occurrences_30m,
            "last_decision": last_decision,
            "cooldown": cooldown,
        },
    }
