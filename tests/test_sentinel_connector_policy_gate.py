from __future__ import annotations

import json
from pathlib import Path

from tools.gates.sentinel_connector_policy_gate import gate_payload


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_policy() -> dict:
    return _load_json_or_yaml("docs/governance/policies/POLICY-CONNECTOR-SENTINEL-OBSERVER-v1.yml")


def _load_json_or_yaml(path: str) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    # policy file is yaml; use very small parser dependency via json fallback not possible
    import yaml
    data = yaml.safe_load(text)
    assert isinstance(data, dict)
    return data


def test_valid_intent_ok_passes() -> None:
    payload = _load_json("tests/fixtures/intent_ok.json")
    out = gate_payload(payload, _load_policy())
    assert out["status"] == "PASS"
    assert out["reason"] == "PASS"
    assert out["offending_paths"] == []


def test_forbidden_fields_fail_closed() -> None:
    payload = _load_json("tests/fixtures/intent_forbidden_fields.json")
    out = gate_payload(payload, _load_policy())
    assert out["status"] == "FAIL_CLOSED"
    assert out["reason"] == "POLICY_VIOLATION"
    assert out["offending_paths"]


def test_policy_mismatch_domain_fails_closed() -> None:
    payload = _load_json("tests/fixtures/intent_ok.json")
    payload["producer"]["domain"] = "other_domain"
    out = gate_payload(payload, _load_policy())
    assert out["status"] == "FAIL_CLOSED"
    assert out["reason"] == "POLICY_VIOLATION"
    assert "$.producer.domain" in out["offending_paths"]
