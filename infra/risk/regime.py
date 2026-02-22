from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


DOWNGRADE_HOLD_MS = 6 * 60 * 60 * 1000
DOWNGRADE_STABLE_MS = 2 * 60 * 60 * 1000
DEFAULT_MISSING = ["vix", "dxy", "real10y", "btcvol"]
STATE_FILE = Path("var/metaos/state/risk_regime_state.json")


class RiskRegime(str, Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    SHOCK = "SHOCK"
    BLACK_SWAN = "BLACK_SWAN"


@dataclass
class RegimeMeta:
    current_regime: RiskRegime
    target_regime: RiskRegime
    reasons: list[str]
    missing: list[str]
    entered_at_ms: int
    normalized_since_ms: int | None
    normalized_for_ms: int
    cooldown_remaining_ms: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "current_regime": self.current_regime.value,
            "target_regime": self.target_regime.value,
            "reasons": self.reasons,
            "missing": self.missing,
            "entered_at": self.entered_at_ms,
            "normalized_since": self.normalized_since_ms,
            "normalized_for_ms": self.normalized_for_ms,
            "cooldown_remaining_ms": self.cooldown_remaining_ms,
        }


def regime_severity(regime: RiskRegime) -> int:
    return {
        RiskRegime.NORMAL: 0,
        RiskRegime.WARNING: 1,
        RiskRegime.SHOCK: 2,
        RiskRegime.BLACK_SWAN: 3,
    }[regime]


class RegimeWarden:
    def __init__(self, state_file: Path = STATE_FILE) -> None:
        self._state_file = state_file
        self.current_regime: RiskRegime = RiskRegime.SHOCK
        self.entered_at_ms: int = 0
        self.normalized_since_ms: int | None = None
        self._normalized_target: RiskRegime | None = None
        self._last_target: RiskRegime = self.current_regime
        self._last_reasons: list[str] = ["uninitialized_fail_closed"]
        self._last_missing: list[str] = list(DEFAULT_MISSING)
        self._load_state()

    def _load_state(self) -> None:
        if not self._state_file.exists():
            return
        try:
            raw = json.loads(self._state_file.read_text(encoding="utf-8"))
            self.current_regime = RiskRegime(str(raw.get("current_regime", RiskRegime.SHOCK.value)))
            self.entered_at_ms = int(raw.get("entered_at_ms", 0))
            ns = raw.get("normalized_since_ms")
            self.normalized_since_ms = int(ns) if ns is not None else None
            nt = raw.get("normalized_target")
            self._normalized_target = RiskRegime(str(nt)) if nt else None
            lt = raw.get("last_target")
            self._last_target = RiskRegime(str(lt)) if lt else self.current_regime
            self._last_reasons = [str(x) for x in raw.get("last_reasons", self._last_reasons)]
            self._last_missing = [str(x) for x in raw.get("last_missing", self._last_missing)]
        except Exception:
            # Fail-closed default state.
            self.current_regime = RiskRegime.SHOCK
            self.entered_at_ms = 0
            self.normalized_since_ms = None
            self._normalized_target = None
            self._last_target = RiskRegime.SHOCK
            self._last_reasons = ["state_load_error_fail_closed"]
            self._last_missing = list(DEFAULT_MISSING)

    def _save_state(self) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "current_regime": self.current_regime.value,
            "entered_at_ms": self.entered_at_ms,
            "normalized_since_ms": self.normalized_since_ms,
            "normalized_target": self._normalized_target.value if self._normalized_target else None,
            "last_target": self._last_target.value,
            "last_reasons": self._last_reasons,
            "last_missing": self._last_missing,
        }
        self._state_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def calculate_target(self, gate_count: int, missing: list[str], hard_kill: bool) -> RiskRegime:
        if hard_kill:
            return RiskRegime.BLACK_SWAN
        if missing:
            return RiskRegime.SHOCK
        if gate_count >= 3:
            return RiskRegime.BLACK_SWAN
        if gate_count == 2:
            return RiskRegime.SHOCK
        if gate_count == 1:
            return RiskRegime.WARNING
        return RiskRegime.NORMAL

    def update(self, now_ms: int, gate_count: int, missing: list[str], hard_kill: bool) -> RegimeMeta:
        reasons: list[str] = [f"gate_count={int(gate_count)}"]
        if missing:
            reasons.append("missing_inputs_fail_closed")
        if hard_kill:
            reasons.append("hard_kill_switch")

        target = self.calculate_target(gate_count=gate_count, missing=missing, hard_kill=hard_kill)
        self._last_target = target
        self._last_reasons = list(reasons)
        self._last_missing = list(missing)

        if self.entered_at_ms <= 0:
            self.entered_at_ms = now_ms

        current_sev = regime_severity(self.current_regime)
        target_sev = regime_severity(target)
        normalized_for_ms = 0
        cooldown_remaining_ms = 0

        if target_sev >= current_sev:
            if target != self.current_regime:
                self.current_regime = target
                self.entered_at_ms = now_ms
            self.normalized_since_ms = None
            self._normalized_target = None
        else:
            if self._normalized_target != target:
                self._normalized_target = target
                self.normalized_since_ms = now_ms
            normalized_for_ms = max(0, now_ms - int(self.normalized_since_ms or now_ms))
            held_for_ms = max(0, now_ms - self.entered_at_ms)
            cooldown_remaining_ms = max(0, DOWNGRADE_HOLD_MS - held_for_ms, DOWNGRADE_STABLE_MS - normalized_for_ms)
            if cooldown_remaining_ms <= 0:
                self.current_regime = target
                self.entered_at_ms = now_ms
                self.normalized_since_ms = None
                self._normalized_target = None
                normalized_for_ms = 0

        self._save_state()
        return RegimeMeta(
            current_regime=self.current_regime,
            target_regime=target,
            reasons=reasons,
            missing=list(missing),
            entered_at_ms=self.entered_at_ms,
            normalized_since_ms=self.normalized_since_ms,
            normalized_for_ms=normalized_for_ms,
            cooldown_remaining_ms=cooldown_remaining_ms,
        )

    def snapshot(self, now_ms: int | None = None) -> RegimeMeta:
        ts = int(now_ms or 0)
        normalized_for_ms = 0
        if ts and self.normalized_since_ms is not None:
            normalized_for_ms = max(0, ts - self.normalized_since_ms)

        return RegimeMeta(
            current_regime=self.current_regime,
            target_regime=self._last_target,
            reasons=list(self._last_reasons),
            missing=list(self._last_missing),
            entered_at_ms=self.entered_at_ms,
            normalized_since_ms=self.normalized_since_ms,
            normalized_for_ms=normalized_for_ms,
            cooldown_remaining_ms=0,
        )


_WARDEN: RegimeWarden | None = None


def get_regime_warden() -> RegimeWarden:
    global _WARDEN
    if _WARDEN is None:
        _WARDEN = RegimeWarden()
    return _WARDEN
