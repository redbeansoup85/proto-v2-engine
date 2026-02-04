from core.observer import observer_hook


def test_emit_shadow_observation_never_raises(monkeypatch):
    def boom(_event):
        raise RuntimeError("sink down")

    monkeypatch.setattr(observer_hook, "emit_audit_event", boom)
    observer_hook.emit_shadow_observation(
        outcome="deny",
        reason_code="SHADOW_ERROR",
        adapter_name="mock",
    )
