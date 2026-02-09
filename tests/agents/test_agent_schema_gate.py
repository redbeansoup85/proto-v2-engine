from __future__ import annotations

import pytest

from auralis_v1.core.agents.agent_schema_gate import validate_agent_output


def test_valid_output_passes() -> None:
    payload = {
        "summary": "short summary",
        "normalized_text": "normalized",
        "highlights": ["a", "b"],
    }
    out = validate_agent_output("fast", payload)
    assert out["summary"] == "short summary"


def test_forbidden_key_fails() -> None:
    payload = {
        "summary": "x",
        "normalized_text": "y",
        "highlights": [],
        "ExEcUtE": "no",
    }
    with pytest.raises(RuntimeError, match=r"forbidden output key: ExEcUtE"):
        validate_agent_output("fast", payload)


def test_extra_field_fails() -> None:
    payload = {
        "summary": "x",
        "normalized_text": "y",
        "highlights": [],
        "extra": "not allowed",
    }
    with pytest.raises(RuntimeError, match="extra keys not allowed"):
        validate_agent_output("fast", payload)
