from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def _load_module() -> Any:
    root = Path(__file__).resolve().parents[2]
    mod_path = root / "tools" / "sentinel_build_summary.py"
    spec = importlib.util.spec_from_file_location("sentinel_build_summary", mod_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_domain_event(
    base: Path,
    symbol: str,
    tf: str,
    ts: str,
    *,
    evidence_ok: bool,
    proof_errors: List[Dict[str, Any]],
) -> None:
    p = base / symbol
    p.mkdir(parents=True, exist_ok=True)
    event = {
        "schema": "domain_event.v1",
        "domain": "sentinel",
        "kind": "SIGNAL",
        "event_id": f"evt-{symbol}-{tf}-{ts}",
        "ts_iso": "2026-02-15T12:00:00Z",
        "signal": {
            "type": "SENTINEL_SIGNAL",
            "symbol": symbol,
            "timeframe": tf,
            "score": 80,
            "confidence": 0.8,
            "risk_level": "medium",
            "direction": "long",
        },
        "meta": {"producer": "test", "version": "1", "build_sha": "abcdef1"},
        "evidence_refs": [
            {
                "ref_kind": "FILEPATH",
                "ref": f"/tmp/metaos_snapshots/{symbol}_{tf}/snapshot_{ts}.json",
            }
        ],
        # extension field for quality extraction path
        "evidence": {
            "ok": evidence_ok,
            "proof_errors": proof_errors,
        },
    }
    (p / f"domain_event_{ts}_{tf}.json").write_text(json.dumps(event, ensure_ascii=False), encoding="utf-8")


def test_build_summary_quality_rollup_v0_compat(tmp_path: Path, monkeypatch) -> None:
    mod = _load_module()
    # The summary tool validates against domain_event.v1 schema that does not include "evidence".
    # Patch validator to focus this test on summary quality aggregation behavior.
    monkeypatch.setattr(mod, "_validate_domain_event", lambda repo_root, event_path: None)

    ts = "20260215T120000Z"
    domain_root = tmp_path / "domain"
    out_path = tmp_path / "summary.json"

    _write_domain_event(
        domain_root,
        "BTCUSDT",
        "15m",
        ts,
        evidence_ok=True,
        proof_errors=[{"type": "stale_limit_default_applied", "severity": "warn"}],
    )
    _write_domain_event(
        domain_root,
        "BTCUSDT",
        "1h",
        ts,
        evidence_ok=False,
        proof_errors=[{"type": "stale_limit_env_parse_error", "severity": "error"}],
    )

    argv = [
        "sentinel_build_summary.py",
        "--ts",
        ts,
        "--symbols",
        "BTCUSDT",
        "--tfs",
        "15m 1h",
        "--domain-root",
        str(domain_root),
        "--out",
        str(out_path),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    rc = mod.main()
    assert rc == 0

    summary = json.loads(out_path.read_text(encoding="utf-8"))
    assert summary["schema"] == "sentinel_summary.v0"
    assert isinstance(summary["items"], list) and len(summary["items"]) == 1

    quality = summary["items"][0]["quality"]
    assert quality["evidence_ok"] is False
    assert quality["error_count"] == 1
    assert quality["warn_count"] == 1
    assert quality["severity_max"] == "error"

    rollup = summary["rollup"]
    assert rollup["error_total"] == 1
    assert rollup["warn_total"] == 1
    assert rollup["ok_count"] == 0
    assert rollup["bad_count"] == 1
    assert rollup["bad_symbols"] == ["BTCUSDT"]
