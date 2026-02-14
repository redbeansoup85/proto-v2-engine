# Sentinel Execution Trigger v0

## Inputs
- summary.items[*].final.{final_score, final_direction, final_risk_level, final_confidence}
- optional: oi_delta_pct (if present)

## Trigger (EXECUTE)
EXECUTE when all conditions hold:
- final_score >= 75
- final_direction in {"long","short"}
- final_risk_level in {"low","medium"}
- final_confidence >= 0.70

Safety veto:
- if oi_delta_pct is present and oi_delta_pct <= -0.20 then NO_TRADE

## Output
- execution_intent.v1 written to outbox
- If not triggered: write a NO_ACTION record (not fail-closed)
