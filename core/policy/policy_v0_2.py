from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.contracts import EngineDecision, EngineSignal, Severity


# -------------------------
# helpers
# -------------------------

_SEV_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_ORDER_TO_SEV = {v: k for k, v in _SEV_ORDER.items()}


def _sev_str(sev: Any) -> str:
    # Severity enum or string -> normalized string
    if hasattr(sev, "value"):
        return str(sev.value)
    return str(sev or "low").lower()


def _sev_max(a: str, b: str) -> str:
    return a if _SEV_ORDER.get(a, 0) >= _SEV_ORDER.get(b, 0) else b


def _sev_step_up(sev: str, n: int = 1) -> str:
    v = min(_SEV_ORDER.get(sev, 0) + n, 3)
    return _ORDER_TO_SEV[v]


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    # expects '...Z' or isoformat
    try:
        if ts.endswith("Z"):
            ts = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts).astimezone(timezone.utc)
    except Exception:
        return None


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _now_iso_fallback(meta_ts_end_iso: Optional[str] = None) -> str:
    dt = _parse_iso(meta_ts_end_iso)
    if dt:
        return _iso(dt)
    return _iso(datetime.now(timezone.utc))


def _cooldown_minutes(channel: Optional[str], severity: str) -> int:
    ch = (channel or "").lower()
    sev = (severity or "low").lower()

    # 기본값
    if sev == "critical":
        base = 10
    elif sev == "high":
        base = 5
    elif sev == "medium":
        base = 2
    else:
        base = 0

    # 채널별 정책
    if ch == "childcare":
        # childcare는 안전 우선: HOLD가 잦지 않도록 충분히 쿨다운
        return max(base, 10 if sev in ("high", "critical") else 5)
    if ch == "trading":
        # trading은 실행 금지지만 알림은 빠르게
        return max(0, min(base, 2))
    if ch == "fnb":
        return max(base, 5 if sev == "critical" else base)

    return base


def _risk_occurrence_increment(current_sev: str) -> int:
    # 스켈레톤: high/critical이면 이번 윈도우를 "위험 발생"으로 1 카운트
    return 1 if current_sev in ("high", "critical") else 0


# -------------------------
# output contract (pure)
# -------------------------

@dataclass(frozen=True)
class PolicyV0_2Result:
    decision: EngineDecision
    temporal_patch: Dict[str, Any]  # scene_state.temporal 에 merge할 패치


# -------------------------
# core logic (pure function)
# -------------------------

def compute_policy_v0_2(
    *,
    channel: Optional[str],
    current_decision: EngineDecision,
    signals: List[EngineSignal],
    prev_scene_state: Optional[Dict[str, Any]] = None,
    now_ts_iso: Optional[str] = None,
) -> PolicyV0_2Result:
    """
    Policy v0.2 (PURE)
    - accumulation: 연속 위험 발생시 severity 단계 상승(스켈레톤)
    - decay: 이 단계에서는 '설계만' 먼저 고정(실제 decay는 메모리/history 도입 후 강화)
    - cooldown: 채널×severity 기반 until_ts 계산
    """

    # 1) 현재 severity(엔진/정책 v0.1 결과)를 문자열로 정규화
    cur_sev = _sev_str(getattr(current_decision, "severity", None))

    # 2) prev temporal 읽기
    prev_temporal = (prev_scene_state or {}).get("temporal") or {}
    prev_last_sev = str(prev_temporal.get("last_severity") or (prev_scene_state or {}).get("summary", {}).get("current_severity") or cur_sev).lower()
    prev_occ_10 = int(prev_temporal.get("occurrences_10m") or 0)
    prev_occ_30 = int(prev_temporal.get("occurrences_30m") or 0)

    # 3) accumulation (스켈레톤)
    # - high/critical이 연속되면 +1 단계(최대 critical)
    effective_sev = cur_sev
    if prev_last_sev in ("high", "critical") and cur_sev in ("high", "critical"):
        # 연속 위험: 한 단계 가중 (high->critical, critical 유지)
        if cur_sev != "critical":
            effective_sev = _sev_step_up(cur_sev, 1)

    # 4) occurrences update (스켈레톤)
    inc = _risk_occurrence_increment(effective_sev)
    occ_10 = prev_occ_10 + inc
    occ_30 = prev_occ_30 + inc

    # 5) trend
    if _SEV_ORDER.get(effective_sev, 0) > _SEV_ORDER.get(prev_last_sev, 0):
        trend = "rising"
    elif _SEV_ORDER.get(effective_sev, 0) < _SEV_ORDER.get(prev_last_sev, 0):
        trend = "falling"
    else:
        trend = "stable"

    # 6) cooldown 계산
    # now_ts_iso가 없으면 meta.ts_end_iso 기반으로 넣어주는 게 이상적이지만,
    # 여기선 pure 함수를 유지하기 위해 caller가 넣도록 하고, 없으면 utc now 사용
    now_iso = now_ts_iso or _now_iso_fallback(None)
    now_dt = _parse_iso(now_iso) or datetime.now(timezone.utc)

    cd_min = _cooldown_minutes(channel, effective_sev)
    until_iso = _iso(now_dt + timedelta(minutes=cd_min)) if cd_min > 0 else None

    cooldown = {
        "until_ts_iso": until_iso,
        "reason": f"{(channel or 'unknown').lower()}_{effective_sev}_cooldown" if until_iso else None,
    }

    # 7) decision severity bump 반영 (mode는 유지; severity만 강화)
    # EngineDecision.severity는 enum이므로, Severity로 변환
    sev_enum = {
        "low": Severity.LOW,
        "medium": Severity.MEDIUM,
        "high": Severity.HIGH,
        "critical": Severity.CRITICAL,
    }[effective_sev]

    if sev_enum != current_decision.severity:
        decision = EngineDecision(
            mode=current_decision.mode,
            severity=sev_enum,
            rationale=list(current_decision.rationale) + [f"policy_v0.2: accumulation → {effective_sev}"],
        )
    else:
        decision = current_decision

    temporal_patch = {
        "last_severity": effective_sev,              # 다음 윈도우 기준점
        "severity_trend": trend,
        "occurrences_10m": occ_10,
        "occurrences_30m": occ_30,
        "last_decision": {
            "mode": getattr(current_decision.mode, "value", None) or str(current_decision.mode),
            "severity": _sev_str(current_decision.severity),
            "ts_iso": now_iso,
        },
        "cooldown": cooldown,
    }

    return PolicyV0_2Result(decision=decision, temporal_patch=temporal_patch)
