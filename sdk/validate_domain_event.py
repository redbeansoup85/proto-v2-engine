from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python sdk/validate_domain_event.py <event.json>")
        return 2

    event_path = Path(sys.argv[1])
    schema_path = Path(__file__).resolve().parent / "schemas" / "domain_event.v1.json"

    try:
        import jsonschema
    except Exception:
        print("FAIL-CLOSED: jsonschema dependency is missing")
        return 1

    try:
        event = json.loads(event_path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"FAIL-CLOSED: cannot load input/schema: {e}")
        return 1

    try:
        jsonschema.validate(instance=event, schema=schema)
    except jsonschema.ValidationError as e:
        print(f"FAIL-CLOSED: domain_event.v1 validation error: {e.message}")
        return 1

    print("OK: domain_event.v1 valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
