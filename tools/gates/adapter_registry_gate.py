from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Finding:
    rule_id: str
    file: str
    message: str


def _load_yaml_or_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"Registry not found: {path}")

    if path.suffix.lower() in [".yaml", ".yml"]:
        try:
            import yaml  # type: ignore
        except Exception as e:
            raise RuntimeError(f"PyYAML required but not available: {e}") from e

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return json.loads(json.dumps(data, ensure_ascii=False, sort_keys=True))

    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))

    raise RuntimeError(f"Unsupported registry extension: {path.suffix}")


def run_gate(*, registry_path: Path, schema_path: Path) -> List[Finding]:
    try:
        registry = _load_yaml_or_json(registry_path)
    except Exception as e:
        return [Finding("REGISTRY_PARSE_FAIL", str(registry_path), str(e))]

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as e:
        return [Finding("SCHEMA_PARSE_FAIL", str(schema_path), str(e))]

    try:
        from jsonschema import Draft202012Validator  # type: ignore
    except Exception as e:
        return [Finding("JSONSCHEMA_MISSING", str(schema_path), f"jsonschema not available: {e}")]

    v = Draft202012Validator(schema)
    errors = sorted(v.iter_errors(registry), key=lambda er: list(er.path))

    findings: List[Finding] = []
    if errors:
        for er in errors[:50]:
            loc = "$" + "".join([f"[{repr(p)}]" for p in er.path])
            findings.append(Finding("REGISTRY_SCHEMA_FAIL", str(registry_path), f"{loc}: {er.message}"))
        return findings

    # extra invariants
    entries = registry.get("entries", [])
    seen = set()
    for e in entries:
        card_id = str(e.get("card_id", "")).strip()
        if card_id in seen:
            findings.append(Finding("DUP_CARD_ID", str(registry_path), f"duplicate card_id: {card_id}"))
        seen.add(card_id)

        adapter_path = str(e.get("adapter_path", "")).strip()
        if not adapter_path:
            findings.append(Finding("EMPTY_ADAPTER_PATH", str(registry_path), f"{card_id}: empty adapter_path"))

    return findings


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--registry", default="policies/adapter_registry.yaml")
    p.add_argument("--schema", default="contracts/adapter_registry.schema.json")
    args = p.parse_args(argv)

    findings = run_gate(registry_path=Path(args.registry), schema_path=Path(args.schema))

    if findings:
        print("FAIL: adapter registry gate (fail-closed)")
        for f in findings:
            print(json.dumps({"rule_id": f.rule_id, "file": f.file, "message": f.message}, ensure_ascii=False))
        return 1

    print("PASS: adapter registry gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
