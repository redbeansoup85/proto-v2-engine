from __future__ import annotations

from core.judgment import DpaOption, SimpleStaticComposer, DecisionStatus


def test_static_composer_builds_dpa_created():
    composer = SimpleStaticComposer(
        options=[DpaOption(option_id="opt_1", title="Option 1")],
        constraints={"l4": ["NO_AUTO_AUTHORIZE"]},
        system_position={"confidence": 0.5},
    )

    dpa = composer.compose(
        dpa_id="dpa_100",
        event_id="evt_100",
        context={"event": {"id": "evt_100"}},
    )

    assert dpa.status == DecisionStatus.DPA_CREATED
    assert dpa.context_json["event"]["id"] == "evt_100"
    assert len(dpa.options_json) == 1
    assert dpa.constraints_json["l4"] == ["NO_AUTO_AUTHORIZE"]
    assert dpa.system_position_json["confidence"] == 0.5
