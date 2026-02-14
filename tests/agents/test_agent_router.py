from __future__ import annotations

from auralis_v1.core.agents.router import resolve_agent, route_agent


def test_route_agent_reasoning() -> None:
    assert route_agent("reasoning") == "reasoning"


def test_route_agent_design() -> None:
    assert route_agent("design") == "design"


def test_route_agent_default_fast() -> None:
    assert route_agent("anything_else") == "fast"
    assert route_agent(None) == "fast"


def test_resolve_agent_fast() -> None:
    out = resolve_agent("other")
    assert out["agent_key"] == "fast"
    assert out["provider"] == "ollama"
