from pprint import pprint

import json
from dataclasses import asdict, is_dataclass

from pathlib import Path

def to_json_safe(obj):
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, dict):
        return {k: to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_json_safe(x) for x in obj]
    return obj
from core.engine.run_engine import run_engine
from core.orchestrator.input_adapters.engine_v0_1 import EngineV01Adapter
from core.orchestrator.routing.recommendation_router import RecommendationRouter


class FakePreludeOutput:
    """
    strict prelude_adapter + emotion_os + orchestrator v0.3까지 통과하는 smoke 입력.
    channel만 바꿔가며 분기 테스트.
    """
    def __init__(self, channel: str) -> None:
        self.ts_start_iso = "2025-12-15T10:00:00Z"
        self.ts_end_iso = "2025-12-15T10:05:00Z"
        self.channel = channel

        self.meta = {
            "org_id": "org-123",
            "site_id": "site-abc",
            "source": "meta-prelude",
            "ts_start_iso": self.ts_start_iso,
            "ts_end_iso": self.ts_end_iso,
            "scene_id": None,
            "channel": self.channel,
        }

        # decision
        self.mode = "observe_more"
        self.severity = "medium"
        self.rationale = [
            "Prelude C not implemented",
            "Default conservative decision",
        ]
        self.decision = {
            "mode": self.mode,
            "severity": self.severity,
            "rationale": list(self.rationale),
        }

        # quality
        self.quality = {
            "quality_score": 0.95,
            "missing_ratio": 0.02,
            "window_sec": 300,
        }

        # uncertainty
        self.uncertainty = {
            "uncertainty_score": 0.1,
            "confidence_score": 0.9,
        }

        # features (emotion_os)
        self.features = {
            "valence": -0.8,
            "arousal": 0.7,
            "dominant_emotion": "distress",
            "child_negative_emotion_score": 0.92,
        }


def run_case(channel: str) -> None:
    print("\n" + "=" * 80)
    print(f"CASE: channel = {channel}")
    print("=" * 80)

    prelude = FakePreludeOutput(channel=channel)
    out = run_engine(prelude)

    print("\nDECISION:")
    pprint(
        {
            "mode": out.decision.mode.value,
            "severity": out.decision.severity.value,
            "rationale": out.decision.rationale,
        }
    )

    print("\nSIGNALS:")
    pprint(
        [
            {
                "type": s.type.value,
                "name": s.name,
                "severity": s.severity.value,
                "confidence": s.confidence,
            }
            for s in out.signals
        ]
    )

    print("\nSCENE_STATE:")
    pprint(out.scene_state)

    print("\nRECOMMENDATIONS:")
    pprint(out.recommendations)

    adapter = EngineV01Adapter()
    orch_in = adapter.adapt(out)

    router = RecommendationRouter()
    decision = router.route(
        orch_in.channel,
        orch_in.severity,
        orch_in.decision_mode,
        orch_in.recommendations,
        meta={"org_id": orch_in.org_id, "site_id": orch_in.site_id},
    )

    print("\nORCHESTRATOR_DECISION (v0.3):")
    pprint(decision)

    # ---- JSON snapshot (docs/demo) ----
    out_dir = Path("docs/demo")
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "channel": channel,
        "decision": to_json_safe(decision),
    }
    out_path = out_dir / f"v0_3_{channel}.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\n[JSON_SNAPSHOT] saved -> {out_path}")


def main() -> None:
    # 3종 분기 테스트
    run_case("childcare")
    run_case("fnb")
    run_case("trading")


if __name__ == "__main__":
    main()