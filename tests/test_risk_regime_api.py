from __future__ import annotations

from types import SimpleNamespace

from infra.api.routes import risk


def test_risk_regime_api_returns_snapshot(monkeypatch) -> None:
    fake = SimpleNamespace(
        snapshot=lambda now_ms=None: SimpleNamespace(
            as_dict=lambda: {
                "current_regime": "WARNING",
                "target_regime": "SHOCK",
                "reasons": ["gate_count=1"],
                "missing": [],
                "entered_at": 123,
                "normalized_since": 100,
                "cooldown_remaining_ms": 456,
            }
        )
    )
    monkeypatch.setattr(risk, "get_regime_warden", lambda: fake)
    out = risk.get_risk_regime()
    assert out["current_regime"] == "WARNING"
    assert out["target_regime"] == "SHOCK"
    assert out["cooldown_remaining_ms"] == 456
