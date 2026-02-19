from __future__ import annotations

import json
from pathlib import Path

from tools.gates.gate_provider_ingest import get_allowed_schema_ids
from tools.gates.gate_schema_registry import compute_sha256, load_registry, verify_registry


def test_registry_verifies_when_hashes_match() -> None:
    assert verify_registry() == []


def test_registry_fails_on_constitution_change(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "schemas").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tools" / "gates").mkdir(parents=True, exist_ok=True)

    constitution_file = tmp_path / "docs" / "LOCK-INTERFACE-CONSTITUTION.md"
    envelope_file = tmp_path / "schemas" / "observer_event_envelope.v1.schema.json"
    provider_gate_file = tmp_path / "tools" / "gates" / "gate_provider_ingest.py"

    constitution_file.write_text("constitution\n", encoding="utf-8")
    envelope_file.write_text('{"type":"object"}\n', encoding="utf-8")
    provider_gate_file.write_text("ALLOWED_SCHEMA_IDS = []\n", encoding="utf-8")

    registry_path = tmp_path / "schemas" / "schema_registry.lock.json"
    registry_path.write_text(
        json.dumps(
            {
                "lock_version": "1.0",
                "generated_at_utc": "2026-02-19T00:00:00Z",
                "allowed_provider_schema_ids": ["sentinel_raw_snapshot.v1"],
                "envelope_schema": {
                    "schema_id": "observer_event_envelope.v1",
                    "schema_file": "schemas/observer_event_envelope.v1.schema.json",
                    "sha256": compute_sha256(envelope_file),
                },
                "provider_gate": {
                    "name": "provider_ingest_gate.v1",
                    "file": "tools/gates/gate_provider_ingest.py",
                    "sha256": compute_sha256(provider_gate_file),
                },
                "constitution": {
                    "file": "docs/LOCK-INTERFACE-CONSTITUTION.md",
                    "sha256": compute_sha256(constitution_file),
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    constitution_file.write_text("constitution changed\n", encoding="utf-8")
    violations = verify_registry(str(registry_path))
    assert any(v["reason"] == "sha_mismatch" and v["path"] == "constitution.sha256" for v in violations)


def test_provider_gate_allowlist_matches_registry() -> None:
    registry = load_registry("schemas/schema_registry.lock.json")
    expected = registry["allowed_provider_schema_ids"]
    got = get_allowed_schema_ids(Path("schemas/schema_registry.lock.json"))
    assert got == expected
