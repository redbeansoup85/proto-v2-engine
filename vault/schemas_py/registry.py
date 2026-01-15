from __future__ import annotations

from typing import Dict, Any

AALLOWED_SCHEMAS: Dict[str, str] = {
    "context_snapshot": "0.1.0",
    "card_definition": "0.1.0",
    "execution_log": "0.1.0",
    "outcome_record": "0.1.0",
    "card_patch": "0.1.0",
    "exception_report": "0.1.0",

    # ✅ add this
    "family_trading_session_log": "1.0.0",
}


def validate_schema(schema: Any) -> bool:
    """
    schema must be {"name": "...", "version": "..."}
    """
    if not isinstance(schema, dict):
        return False
    name = schema.get("name")
    ver = schema.get("version")
    if not isinstance(name, str) or not isinstance(ver, str):
        return False
    return ALLOWED_SCHEMAS.get(name) == ver
