# vault/family_trading.py
from __future__ import annotations

from typing import List, Dict, Optional, Literal, Any
from pydantic import BaseModel, Field, confloat

# --- schema ref (matches vault/registry.py contract) ---
class SchemaRef(BaseModel):
    name: Literal["family_trading_session_log"]
    version: Literal["1.0.0"]


Bias = Literal["bull", "bear", "neutral", "n/a"]
State = Literal["up", "down", "flat", "positive", "negative", "neutral", "n/a"]
Decision = Literal["NO_TRADE", "LONG", "SHORT", "REDUCE", "HEDGE", "n/a"]
Style = Literal["intraday", "swing", "scalp", "position", "n/a"]
Result = Literal["observed", "win", "loss", "breakeven", "n/a"]


class TimeRange(BaseModel):
    start: str
    end: str


class Meta(BaseModel):
    session_id: str
    captured_at_range: TimeRange
    asset: str
    market: str
    venue: str
    timeframe: str
    session: str
    analyst: str
    source: Literal["screenshots", "manual", "mixed"]
    links: Dict[str, str] = Field(default_factory=dict)


class EvidenceSets(BaseModel):
    chart: List[str] = Field(default_factory=list)
    derivatives: List[str] = Field(default_factory=list)
    heatmap: List[str] = Field(default_factory=list)
    orderbook: List[str] = Field(default_factory=list)


class Trigger(BaseModel):
    types: List[str]
    note: Optional[str] = None


class KeyLevel(BaseModel):
    price: float
    label: str


class Structure(BaseModel):
    htf_bias: Bias
    market_structure: str
    key_levels: List[KeyLevel] = Field(default_factory=list)
    range_context: Literal["range_low_sweep", "range_high_sweep", "trend", "n/a"]
    notes: Optional[str] = None


class MetricState(BaseModel):
    state: State
    note: Optional[str] = None


class DerivativesState(BaseModel):
    oi: MetricState
    funding: MetricState
    long_short: MetricState
    basis: MetricState
    liquidation: MetricState


class TFState(BaseModel):
    bias: Bias
    note: Optional[str] = None


class MTFConsensus(BaseModel):
    is_aligned: bool
    label: Literal["MTF_CONSENSUS_YES", "MTF_CONSENSUS_NO", "n/a"]


class MTF(BaseModel):
    _15m: TFState = Field(alias="15m")
    _1h: TFState = Field(alias="1h")
    _4h: TFState = Field(alias="4h")
    consensus: MTFConsensus


class Environment(BaseModel):
    scene_label: str
    pressure_tags: List[str] = Field(default_factory=list)
    uncertainty: Literal["low", "medium", "high", "n/a"]
    notes: Optional[str] = None


class EvidenceSummary(BaseModel):
    claims: List[str] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)
    missing: List[str] = Field(default_factory=list)


class Observation(BaseModel):
    trigger: Trigger
    structure: Structure
    derivatives_state: DerivativesState
    mtf: MTF
    environment: Environment
    evidence_summary: EvidenceSummary


class Judgment(BaseModel):
    decision: Decision
    style: Style
    confidence: Optional[confloat(ge=0, le=1)] = None
    one_liner: Optional[str] = None
    reasoning: List[str] = Field(default_factory=list)


class Execution(BaseModel):
    executed: bool
    orders: List[Dict[str, Any]] = Field(default_factory=list)
    why: List[str] = Field(default_factory=list)


class Outcome(BaseModel):
    result: Result
    pnl: Optional[str] = None
    duration: Optional[str] = None
    notes: Optional[str] = None


class ExceptionItem(BaseModel):
    type: str
    severity: Literal["high", "medium", "low", "n/a"]
    note: Optional[str] = None


class Review(BaseModel):
    what_was_right: List[str] = Field(default_factory=list)
    what_was_wrong: List[str] = Field(default_factory=list)
    rule_reinforced: List[str] = Field(default_factory=list)
    rule_updates: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class FamilyTradingSessionLog(BaseModel):
    # ✅ IMPORTANT: schema is dict-based (name/version)
    schema: SchemaRef

    meta: Meta
    evidence_sets: EvidenceSets
    observation: Observation
    judgment: Judgment
    execution: Execution
    outcome: Outcome
    exceptions: List[ExceptionItem] = Field(default_factory=list)
    review: Review
