from __future__ import annotations

from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class Source(BaseModel):
    kind: Literal["learning", "human", "external"]
    name: str
    run_id: str
    created_at: str  # ISO8601 string (kept as str to avoid TZ policy conflicts)


class Scope(BaseModel):
    domain: str
    subsystem: str
    severity: Literal["low", "medium", "high"]
    blast_radius: Literal["local", "service", "system", "external"]


class ConstitutionReq(BaseModel):
    required_sections: List[str] = Field(default_factory=lambda: ["AQ"])
    constitution_hash: str


class ObservationWindow(BaseModel):
    mode: Literal["time", "events"]
    t_window: Optional[str] = None
    n_events: Optional[int] = None

    @model_validator(mode="after")
    def _window_consistency(self):
        if self.mode == "time":
            if not self.t_window:
                raise ValueError("observation_window.t_window required when mode='time'")
        if self.mode == "events":
            if self.n_events is None or self.n_events <= 0:
                raise ValueError("observation_window.n_events must be > 0 when mode='events'")
        return self


class SampleReq(BaseModel):
    n_min: int
    n_observed: int


class StabilityReq(BaseModel):
    k_confirmations: int
    epsilon: float
    summary: str


class Preconditions(BaseModel):
    constitution: ConstitutionReq
    observation_window: ObservationWindow
    sample: SampleReq
    stability: StabilityReq


class Baseline(BaseModel):
    policy_snapshot_id: str
    policy_hash: str


class Patch(BaseModel):
    format: Literal["jsonpatch", "mergepatch", "custom"]
    content: Any


class Explain(BaseModel):
    current_policy_summary: str
    proposed_policy_summary: str
    rationale: str
    expected_impact: str
    rollback_scope: str
    risks: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)

    @field_validator(
        "current_policy_summary",
        "proposed_policy_summary",
        "rationale",
        "expected_impact",
        "rollback_scope",
    )
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("explain fields must be non-empty strings")
        return v.strip()


class RateLimit(BaseModel):
    period: str
    limit_x: int
    cooldown: str
    rest_required: bool


class HumanGate(BaseModel):
    required: bool
    reasons: List[str] = Field(default_factory=list)


class PolicyProposal(BaseModel):
    proposal_id: str
    proposal_type: Literal["policy_patch"] = "policy_patch"
    source: Source
    scope: Scope
    preconditions: Preconditions
    baseline: Baseline
    patch: Patch
    explain: Explain
    rate_limit: RateLimit
    human_gate: HumanGate

    @model_validator(mode="after")
    def _basic_consistency(self):
        # conservative guard: under-scoping is a governance risk.
        if self.scope.blast_radius not in {"local", "service", "system", "external"}:
            raise ValueError("invalid scope.blast_radius")
        # baseline hash must exist
        if not self.baseline.policy_hash.strip():
            raise ValueError("baseline.policy_hash must be non-empty")
        return self
