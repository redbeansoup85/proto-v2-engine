from __future__ import annotations

import json
from pathlib import Path

from tools.gates.gate_provider_ingest import validate_provider_envelope


def _write_registry_lockfile(root: Path) -> None:
    p = root / "schemas"
    p.mkdir(parents=True, exist_ok=True)
    (p / "schema_registry.lock.json").write_text(
        json.dumps(
            {
                "allowed_provider_schema_ids": [
                    "sentinel_raw_snapshot.v1",
                    "sentinel_trade_intent.v1",
                    "sentinel_signal_meta.v1",
                    "score_snapshot.v1",
                    "pattern_event.v1",
                ]
            }
        ),
        encoding="utf-8",
    )


def _envelope(*, schema_id: str = "sentinel_raw_snapshot.v1", body: dict | None = None) -> dict:
    return {
        "run_id": "RUN-001",
        "event_id": "EVT-001",
        "ts_utc": "2026-02-19T00:00:00Z",
        "provider": {
            "provider_id": "sentinel",
            "provider_class": "SIGNAL_ONLY",
        },
        "payload": {
            "schema_id": schema_id,
            "schema_version": "v1",
            "body": body if body is not None else {"signal": "observe_only"},
        },
        "hash": {
            "hash_alg": "sha256",
            "payload_hash": "abc123",
        },
    }


def test_accepts_valid_raw_snapshot() -> None:
    env = _envelope(
        schema_id="sentinel_raw_snapshot.v1",
        body={"price": 100, "symbol": "BTCUSDT"},
    )
    assert validate_provider_envelope(env) == []


def test_rejects_non_signal_only_provider_class(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_registry_lockfile(tmp_path)
    env = _envelope()
    env["provider"]["provider_class"] = "EXECUTION"
    out = validate_provider_envelope(env)
    assert len(out) == 1
    assert out[0]["reason"] == "provider_class_must_be_SIGNAL_ONLY"


def test_rejects_non_allowlisted_schema(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_registry_lockfile(tmp_path)
    env = _envelope(schema_id="decision.plan.v1")
    out = validate_provider_envelope(env)
    assert len(out) == 1
    assert out[0]["reason"] == "schema_id_not_allowlisted"


def test_rejects_trade_intent_not_dry_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_registry_lockfile(tmp_path)
    env = _envelope(
        schema_id="sentinel_trade_intent.v1",
        body={"mode": "LIVE", "signal": "buy"},
    )
    out = validate_provider_envelope(env)
    assert len(out) == 1
    assert out[0]["reason"] == "trade_intent_mode_must_be_DRY_RUN"


def test_rejects_forbidden_field_qty(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_registry_lockfile(tmp_path)
    env = _envelope(
        schema_id="sentinel_signal_meta.v1",
        body={"symbol": "BTCUSDT", "qty": 1},
    )
    out = validate_provider_envelope(env)
    assert len(out) == 1
    assert out[0]["reason"] == "forbidden_field_name"
    assert out[0]["path"] == "payload.body.qty"


def test_writes_exception_record_on_reject(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_registry_lockfile(tmp_path)

    env = _envelope()
    env["provider"]["provider_class"] = "EXECUTION"

    out = validate_provider_envelope(env)
    assert len(out) == 1

    p = tmp_path / "Exceptions" / "RUN-001.jsonl"
    assert p.exists()
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    obj = json.loads(lines[0])
    assert obj["provider_id"] == "sentinel"
    assert obj["schema_id"] == "sentinel_raw_snapshot.v1"
    assert isinstance(obj["violations"], list)
    assert len(obj["violations"]) == 1
    assert obj["violations"][0]["reason"] == "provider_class_must_be_SIGNAL_ONLY"
    assert obj["violations"][0]["path"] == "provider.provider_class"
    assert obj["violations"][0]["got"] == "EXECUTION"
