from __future__ import annotations

from dataclasses import is_dataclass
from typing import Any, Dict, Optional, List

from core.contracts import (
    EngineInput,
    EngineMeta,
    PreludeInterpretation,
    QualitySnapshot,
    UncertaintySnapshot,
    EngineDecision,
    EngineOutput,
    EngineSignal,
    DecisionMode,
    Severity,
    SignalType,
)


# =========================================================
# helpers: safe getters / coercion
# =========================================================

def _as_dict(obj: Any) -> Dict[str, Any]:
    """dict / dataclass / pydantic / 일반 객체 모두를 dict-like로 다룬다."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):  # pydantic v2
        return obj.model_dump()
    if hasattr(obj, "dict"):  # pydantic v1
        try:
            return obj.dict()
        except Exception:
            pass
    if is_dataclass(obj):
        return obj.__dict__
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return {}


def _get(obj: Any, *path: str, default: Any = None) -> Any:
    """
    obj에서 path 후보들을 순서대로 탐색한다.
    path는 "a.b.c" 형태도 가능
    """
    if obj is None:
        return default

    base = obj
    for p in path:
        cur = base
        ok = True
        for key in p.split("."):
            if cur is None:
                ok = False
                break
            if isinstance(cur, dict):
                if key in cur:
                    cur = cur[key]
                else:
                    ok = False
                    break
            else:
                if hasattr(cur, key):
                    cur = getattr(cur, key)
                else:
                    ok = False
                    break
        if ok:
            return cur
    return default


def _require(value: Any, name: str, strict: bool, debug: Dict[str, Any]) -> Any:
    if value is None:
        if strict:
            raise ValueError(f"[prelude_adapter] missing required field: {name}")
        debug.setdefault("missing_fields", []).append(name)
    return value


def _coerce_float(x: Any) -> Optional[float]:
    try:
        return None if x is None else float(x)
    except Exception:
        return None


def _coerce_int(x: Any) -> Optional[int]:
    try:
        return None if x is None else int(x)
    except Exception:
        return None


def _coerce_list_str(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, list):
        return [str(v) for v in x]
    return [str(x)]


# =========================================================
# enum coercion
# =========================================================

def _to_decision_mode(x: Any, strict: bool, debug: Dict[str, Any]) -> DecisionMode:
    if x is None:
        return _require(None, "mode", strict, debug)  # type: ignore

    s = str(x).strip().lower()
    alias = {
        "observe": "observe_more",
        "observe_more": "observe_more",
        "need_more_data": "observe_more",
        "hold": "suppress",
        "suppress": "suppress",
        "block": "suppress",
        "allow": "allow",
        "pass": "allow",
        "proceed": "allow",
    }
    if s in alias:
        return DecisionMode(alias[s])

    if strict:
        raise ValueError(f"[prelude_adapter] invalid mode: {x}")
    debug.setdefault("invalid_fields", []).append({"mode": x})
    return DecisionMode.OBSERVE_MORE


def _to_severity(x: Any, strict: bool, debug: Dict[str, Any]) -> Severity:
    if x is None:
        return _require(None, "severity", strict, debug)  # type: ignore

    s = str(x).strip().lower()
    alias = {
        "low": "low",
        "l": "low",
        "medium": "medium",
        "med": "medium",
        "m": "medium",
        "high": "high",
        "h": "high",
        "critical": "critical",
        "crit": "critical",
        "c": "critical",
    }
    if s in alias:
        return Severity(alias[s])

    if strict:
        raise ValueError(f"[prelude_adapter] invalid severity: {x}")
    debug.setdefault("invalid_fields", []).append({"severity": x})
    return Severity.MEDIUM


# =========================================================
# main adapter
# =========================================================

def adapt_prelude_output_to_engine_input(
    prelude_output: Any,
    *,
    strict: bool = True,
    source: str = "meta-prelude",
) -> EngineInput:
    """
    meta-prelude 최종 출력 → EngineInput 변환
    """

    debug: Dict[str, Any] = {}

    # -------------------------
    # meta
    # -------------------------
    org_id = _require(
        _get(prelude_output, "org_id", "meta.org_id", "meta.org"),
        "org_id",
        strict,
        debug,
    )

    site_id = _require(
        _get(prelude_output, "site_id", "meta.site_id", "meta.site"),
        "site_id",
        strict,
        debug,
    )

    ts_start = _require(
        _get(
            prelude_output,
            "ts_start_iso",
            "ts_start",
            "window.start_iso",
            "meta.ts_start_iso",
            "meta.ts_start",
        ),
        "ts_start_iso",
        strict,
        debug,
    )

    ts_end = _require(
        _get(
            prelude_output,
            "ts_end_iso",
            "ts_end",
            "window.end_iso",
            "meta.ts_end_iso",
            "meta.ts_end",
        ),
        "ts_end_iso",
        strict,
        debug,
    )

    scene_id = _get(prelude_output, "scene_id", "meta.scene_id")
    channel = _get(prelude_output, "channel", "meta.channel")

    meta = EngineMeta(
        org_id=str(org_id),
        site_id=str(site_id),
        source=source,
        ts_start_iso=str(ts_start),
        ts_end_iso=str(ts_end),
        scene_id=str(scene_id) if scene_id is not None else None,
        channel=str(channel) if channel is not None else None,
    )

    # -------------------------
    # decision
    # -------------------------
    mode_raw = _get(prelude_output, "mode", "decision.mode", "interpretation.mode")
    sev_raw = _get(prelude_output, "severity", "decision.severity", "interpretation.severity")
    reasons_raw = _get(
        prelude_output,
        "reasons",
        "rationale",
        "decision.reasons",
        "decision.rationale",
    )

    mode = _to_decision_mode(mode_raw, strict, debug)
    severity = _to_severity(sev_raw, strict, debug)
    reasons = _coerce_list_str(reasons_raw)

    # -------------------------
    # quality
    # -------------------------
    window_sec = _coerce_int(_get(prelude_output, "window_sec", "quality.window_sec"))
    missing_ratio = _coerce_float(_get(prelude_output, "missing_ratio", "quality.missing_ratio"))
    quality_score = _coerce_float(_get(prelude_output, "quality_score", "quality.quality_score"))
    anomaly_score = _coerce_float(_get(prelude_output, "anomaly_score", "quality.anomaly_score"))
    notes = _get(prelude_output, "quality_notes", "quality.notes")

    _require(window_sec, "quality.window_sec", strict, debug)
    _require(missing_ratio, "quality.missing_ratio", strict, debug)
    _require(quality_score, "quality.quality_score", strict, debug)

    quality = QualitySnapshot(
        window_sec=window_sec or 0,
        missing_ratio=missing_ratio or 1.0,
        quality_score=quality_score or 0.0,
        anomaly_score=anomaly_score,
        notes=str(notes) if notes is not None else None,
    )

    # -------------------------
    # uncertainty
    # -------------------------
    unc = _coerce_float(_get(prelude_output, "uncertainty_score", "uncertainty.uncertainty_score"))
    conf = _coerce_float(_get(prelude_output, "confidence_score", "uncertainty.confidence_score"))
    ood = _coerce_float(_get(prelude_output, "ood_score", "uncertainty.ood_score"))
    ece = _coerce_float(_get(prelude_output, "ece", "uncertainty.ece"))

    _require(unc, "uncertainty.uncertainty_score", strict, debug)
    _require(conf, "uncertainty.confidence_score", strict, debug)

    uncertainty = UncertaintySnapshot(
        uncertainty_score=unc or 1.0,
        confidence_score=conf or 0.0,
        ood_score=ood,
        ece=ece,
    )

    # -------------------------
    # features / refs
    # -------------------------
    features = _get(prelude_output, "features", "feature_set") or {}
    raw_refs = _get(prelude_output, "raw_refs", "refs", "meta.raw_refs") or {}

    prelude = PreludeInterpretation(
        mode=mode,
        severity=severity,
        reasons=reasons,
        quality=quality,
        uncertainty=uncertainty,
        features=dict(features),
        raw_refs=dict(raw_refs),
    )

    # -------------------------
    # context + debug
    # -------------------------
    context = _get(prelude_output, "context", "meta.context") or {}
    if not isinstance(context, dict):
        context = _as_dict(context)

    if debug:
        context["_adapter_debug"] = debug

    return EngineInput(meta=meta, prelude=prelude, context=context)


# =========================================================
# minimal EngineOutput (smoke test)
# =========================================================

def make_minimal_engine_output(inp: EngineInput) -> EngineOutput:
    decision = EngineDecision(
        mode=inp.prelude.mode,
        severity=inp.prelude.severity,
        rationale=inp.prelude.reasons,
    )

    signals = [
        EngineSignal(
            type=SignalType.QUALITY,
            name="quality_score",
            value=inp.prelude.quality.quality_score,
            severity=inp.prelude.severity,
            confidence=1.0,
            details={"missing_ratio": inp.prelude.quality.missing_ratio},
        ),
        EngineSignal(
            type=SignalType.UNCERTAINTY,
            name="uncertainty_score",
            value=inp.prelude.uncertainty.uncertainty_score,
            severity=inp.prelude.severity,
            confidence=1.0,
            details={"confidence_score": inp.prelude.uncertainty.confidence_score},
        ),
    ]

    return EngineOutput(
        meta=inp.meta,
        decision=decision,
        signals=signals,
        scene_state={},
        recommendations=[],
        debug=inp.context.get("_adapter_debug"),
    )
