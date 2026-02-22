from __future__ import annotations

from infra.risk.regime import RegimeWarden, RiskRegime


def test_escalates_immediately(tmp_path) -> None:
    w = RegimeWarden(state_file=tmp_path / "regime_state.json")
    base = 1_000_000
    w.current_regime = RiskRegime.NORMAL
    w.entered_at_ms = base
    out2 = w.update(now_ms=base + 1, gate_count=2, missing=[], hard_kill=False)
    assert out2.current_regime == RiskRegime.SHOCK


def test_downgrade_requires_6h_and_2h_stability(tmp_path) -> None:
    w = RegimeWarden(state_file=tmp_path / "regime_state.json")
    t0 = 2_000_000
    w.update(now_ms=t0, gate_count=2, missing=[], hard_kill=False)

    before_6h = w.update(now_ms=t0 + (6 * 60 * 60 * 1000) - 1, gate_count=0, missing=[], hard_kill=False)
    assert before_6h.current_regime == RiskRegime.SHOCK

    before_2h = w.update(now_ms=t0 + (6 * 60 * 60 * 1000) + (2 * 60 * 60 * 1000) - 2, gate_count=0, missing=[], hard_kill=False)
    assert before_2h.current_regime == RiskRegime.SHOCK

    after = w.update(now_ms=t0 + (8 * 60 * 60 * 1000), gate_count=0, missing=[], hard_kill=False)
    assert after.current_regime == RiskRegime.NORMAL


def test_missing_forces_shock(tmp_path) -> None:
    w = RegimeWarden(state_file=tmp_path / "regime_state.json")
    out = w.update(now_ms=3_000_000, gate_count=0, missing=["vix"], hard_kill=False)
    assert out.current_regime in (RiskRegime.SHOCK, RiskRegime.BLACK_SWAN)
    assert out.target_regime in (RiskRegime.SHOCK, RiskRegime.BLACK_SWAN)


def test_hard_kill_prioritizes_black_swan(tmp_path) -> None:
    w = RegimeWarden(state_file=tmp_path / "regime_state.json")
    out = w.update(now_ms=4_000_000, gate_count=0, missing=[], hard_kill=True)
    assert out.current_regime == RiskRegime.BLACK_SWAN
