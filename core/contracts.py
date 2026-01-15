from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, List


# -------------------------
# Enums (Engine-wide)
# -------------------------

class DecisionMode(str, Enum):
    OBSERVE_MORE = "observe_more"   # 더 관찰/데이터 필요
    SUPPRESS = "suppress"           # 판단/개입 보류
    ALLOW = "allow"                 # 다음 단계(오케스트레이터/실행 후보)로 진행


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SignalType(str, Enum):
    QUALITY = "quality"
    UNCERTAINTY = "uncertainty"
    OOD = "ood"
    CALIBRATION = "calibration"
    SCENE = "scene"
    EMOTION = "emotion"
    POLICY = "policy"


# -------------------------
# Shared primitives
# -------------------------

@dataclass(frozen=True)
class EngineMeta:
    org_id: str
    site_id: str
    source: str                    # e.g. "meta-prelude"
    ts_start_iso: str              # window start (ISO string)
    ts_end_iso: str                # window end (ISO string)
    scene_id: Optional[str] = None
    channel: Optional[str] = None  # e.g. "childcare", "kisetsu"


@dataclass(frozen=True)
class QualitySnapshot:
    window_sec: int
    missing_ratio: float
    quality_score: float           # 0~1
    anomaly_score: Optional[float] = None  # optional
    notes: Optional[str] = None


@dataclass(frozen=True)
class UncertaintySnapshot:
    uncertainty_score: float       # 0~1
    confidence_score: float        # 0~1 (1-uncertainty 형태든 별도든 prelude 기준)
    ood_score: Optional[float] = None
    ece: Optional[float] = None    # calibration proxy


@dataclass(frozen=True)
class PreludeInterpretation:
    """
    meta-prelude의 최종 출력 요약본.
    - prelude의 원본 contract를 그대로 끌고 오기 부담될 때를 대비해
      엔진이 필요한 최소 필드만 '안정적으로' 들고 온다.
    """
    mode: DecisionMode                         # observe_more / suppress / allow
    severity: Severity                         # low~critical
    reasons: List[str]                         # 사람이 읽는 근거 문자열
    quality: QualitySnapshot
    uncertainty: UncertaintySnapshot
    features: Dict[str, Any]                   # prelude에서 계산한 feature set (확장 자유)
    raw_refs: Dict[str, Any]                   # raw file path, batch id 등 참조


# -------------------------
# Engine Input / Output
# -------------------------

@dataclass(frozen=True)
class EngineInput:
    """
    proto-v2-engine의 유일한 입력 계약.
    - meta-prelude 결과를 받아서,
    - 엔진 내부 OS들이 사용할 '공통 컨테이너'로 만든다.
    """
    meta: EngineMeta
    prelude: PreludeInterpretation

    # 엔진 내부에서 추가 컨텍스트(운영 상태, 룰셋 버전 등)가 필요하면 여기에 확장
    context: Dict[str, Any] = None


@dataclass(frozen=True)
class EngineSignal:
    """
    엔진 내부 모듈들이 생산하는 신호의 공통 표현.
    오케스트레이터는 이 신호들을 모아서 정책 적용/충돌 해결을 한다.
    """
    type: SignalType
    name: str
    value: Any
    severity: Severity
    confidence: float              # 0~1
    details: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class EngineDecision:
    """
    엔진이 내리는 '엔진 레벨 판단'.
    실행이 아니라 '다음 단계로 보낼지'와 '왜 그런지'를 고정.
    """
    mode: DecisionMode
    severity: Severity
    rationale: List[str]


@dataclass(frozen=True)
class EngineOutput:
    """
    proto-v2-orchestrator가 그대로 받아 조율할 수 있는 출력 계약.
    """
    meta: EngineMeta
    decision: EngineDecision
    signals: List[EngineSignal]

    # 오케스트레이터/상위 레이어가 활용할 구조화된 상태
    scene_state: Dict[str, Any]                # scene builder 결과(최소 dict로 시작)
    recommendations: List[Dict[str, Any]]      # action 후보(아직 실행 아님)
    debug: Optional[Dict[str, Any]] = None
