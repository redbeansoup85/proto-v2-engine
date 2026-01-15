from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from core.contracts import EngineDecision, EngineSignal, Severity


_SEV_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_ORDER_TO_SEV = {v: k for k, v in _SEV_ORDER.items()}


def _sev_str(sev: Any) -> str:
    if hasattr(sev, "value"):
        return str(sev.value)
    return str(sev or "low").lower()


def _sev_step_down(sev: str, n: int = 1) -> str:
    v = max(_SEV_ORDER.get(sev, 0) - n, 0)
    return _ORDER_TO_SEV[v]


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts).astimezone(timezone.utc)
    except Exception:
        return None


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _cooldown_minutes(channel: Optional[str], severity: str) -> int:
    ch = (channel or "").lower()
    sev = (severity or "low").lower()

    if sev == "critical":
        base = 10
    elif sev == "high":
        base = 5
    elif sev == "medium":
        base = 2
    else:
        base = 0

    if ch == "childcare":
        return max(base, 10 if sev in ("high", "critical") else 5)
    if ch == "trading":
        return max(0, min(base, 2))
    if ch == "fnb":
        return max(base, 5 if sev == "critical" else base)
    return base


def _decay_hold_minutes(channel: Optional[str]) -> int:
    ch = (channel or "").lower()
    if ch == "childcare":
        return 10
    if ch == "fnb":
        return 5
    if ch == "trading":
        return 2
    return 5


def _safe_conditions(signals: List[EngineSignal]) -> bool:
    # 설계 고정: 안전조건(quality/uncertainty + high/critical 부재)
    max_sev = "low"
    q_ok = True
    u_ok = True

    for s in signals:
        sev = _sev_str(getattr(s, "severity", None))
        if _SEV_ORDER.get(sev, 0) > _SEV_ORDER.get(max_sev, 0):
            max_sev = sev

        t = getattr(getattr(s, "type", None), "value", None) or str(getattr(s, "type", ""))
        if t == "quality" and s.name == "quality_score":
            try:
                q_ok = float(getattr(s, "value", 1.0)) >= 0.9
            except Exception:
                pass
        if t == "uncertainty" and s.name in ("confidence_score", "uncertainty_confidence"):
            try:
                u_ok = float(getattr(s, "value", 1.0)) >= 0.7
            except Exception:
                pass

    no_high_risk = max_sev not in ("high", "critical")
    return no_high_risk and q_ok and u_ok


@dataclass(frozen=True)
class PolicyV0_3Result:
    decision: EngineDecision
    temporal_patch: Dict[str, Any]


def compute_policy_v0_3(
    *,
    channel: Optional[str],
    current_decision: EngineDecision,
    signals: List[EngineSignal],
    prev_scene_state: Optional[Dict[str, Any]],
    now_ts_iso: str,
) -> PolicyV0_3Result:
    """
    v0.3 = v0.2(accumulation/cooldown) + decay(설계 고정 버전)
    - decay는 '안전조건 유지시간'이 threshold 이상일 때 1단계 하향
    """
    cur_sev = _sev_str(getattr(current_decision, "severity", None))

    prev_temporal = (prev_scene_state or {}).get("temporal") or {}
    prev_last_sev = str(prev_temporal.get("last_severity") or (prev_scene_state or {}).get("summary", {}).get("current_severity") or cur_sev).lower()
    prev_last_dec = prev_temporal.get("last_decision") or {}
    prev_last_ts = _parse_iso(prev_last_dec.get("ts_iso"))

    now_dt = _parse_iso(now_ts_iso) or datetime.now(timezone.utc)

    # --- decay 판단 ---
    effective_sev = cur_sev
    safe = _safe_conditions(signals)
    if safe and prev_last_ts:
        held_min = (now_dt - prev_last_ts).total_seconds() / 60.0
        if held_min >= _decay_hold_minutes(channel):
            # 1단계만 하향
            effective_sev = _sev_step_down(prev_last_sev, 1)

    # --- cooldown ---
    cd_min = _cooldown_minutes(channel, effective_sev)
    until_iso = _iso(now_dt + timedelta(minutes=cd_min)) if cd_min > 0 else None

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
            rationale=list(current_decision.rationale) + [f"policy_v0.3: decay/cooldown → {effective_sev}"],
        )
    else:
        decision = current_decision

    temporal_patch = {
        "last_severity": effective_sev,
        "last_decision": {
            "mode": getattr(current_decision.mode, "value", None) or str(current_decision.mode),
            "severity": _sev_str(current_decision.severity),
            "ts_iso": now_ts_iso,
        },
        "cooldown": {
            "until_ts_iso": until_iso,
            "reason": f"{(channel or 'unknown').lower()}_{effective_sev}_cooldown" if until_iso else None,
        },
    }

    return PolicyV0_3Result(decision=decision, temporal_patch=temporal_patch)
