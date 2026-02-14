#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _deterministic_mode(ci_flag: bool) -> bool:
    if ci_flag:
        return True
    return any(key.startswith("METAOS_CI_DETERMINISTIC_") for key in os.environ)


def _parse_tags(raw_tags: list[str]) -> list[str]:
    tags: list[str] = []
    for raw in raw_tags:
        for item in raw.split(","):
            tag = item.strip()
            if tag:
                tags.append(tag)
    return tags


def _parse_metrics(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"FAIL-CLOSED: --metrics-json must be valid JSON object: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SystemExit("FAIL-CLOSED: --metrics-json must parse to an object")
    return parsed


def _parse_evidence(entries: list[str]) -> list[dict]:
    refs: list[dict] = []
    for raw in entries:
        parts = raw.replace(",", " ").split()
        kv: dict[str, str] = {}
        for part in parts:
            if "=" not in part:
                raise SystemExit(
                    f"FAIL-CLOSED: --evidence entry must be key=value pairs, got: {raw}"
                )
            key, value = part.split("=", 1)
            kv[key.strip()] = value.strip()
        if set(kv.keys()) != {"ref_kind", "ref"}:
            raise SystemExit(
                f"FAIL-CLOSED: --evidence requires ref_kind and ref only, got keys: {sorted(kv.keys())}"
            )
        refs.append({"ref_kind": kv["ref_kind"], "ref": kv["ref"]})
    return refs


def _build_sha(repo_root: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--verify", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(
            "FAIL-CLOSED: cannot resolve current git SHA for meta.build_sha: "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    sha = proc.stdout.strip()
    if not re.fullmatch(r"[a-fA-F0-9]{7,64}", sha):
        raise SystemExit(f"FAIL-CLOSED: invalid git SHA format for meta.build_sha: {sha}")
    return sha


def _validate_output(repo_root: Path, out_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(repo_root / "sdk" / "validate_domain_event.py"), str(out_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "unknown validation error"
        raise SystemExit(f"FAIL-CLOSED: domain_event.v1 validation failed: {detail}")


def _from_snapshot(snapshot_file: str) -> dict:
    path = Path(snapshot_file)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"FAIL-CLOSED: cannot load --snapshot-file: {exc}") from exc

    if not isinstance(raw, dict):
        raise SystemExit("FAIL-CLOSED: --snapshot-file JSON root must be an object")

    symbol = raw.get("symbol")
    if not isinstance(symbol, str) or not symbol:
        raise SystemExit("FAIL-CLOSED: snapshot.symbol must be a non-empty string")

    score = raw.get("score")
    if not isinstance(score, dict):
        raise SystemExit("FAIL-CLOSED: snapshot.score must be an object")

    final = score.get("final")
    confidence = score.get("confidence")
    risk_level = score.get("risk_level")
    direction = score.get("direction")

    if not isinstance(final, int):
        raise SystemExit("FAIL-CLOSED: snapshot.score.final must be int")
    if not isinstance(confidence, (int, float)):
        raise SystemExit("FAIL-CLOSED: snapshot.score.confidence must be number")
    if risk_level not in {"low", "medium", "high"}:
        raise SystemExit("FAIL-CLOSED: snapshot.score.risk_level must be low|medium|high")
    if direction not in {None, "long", "short", "neutral"}:
        raise SystemExit("FAIL-CLOSED: snapshot.score.direction must be long|short|neutral if present")

    return {
        "symbol": symbol,
        "timeframe": "other",
        "score": int(final),
        "confidence": float(confidence),
        "risk_level": risk_level,
        "direction": direction,
        "tags": ["snapshot_v0_2", "live_loop"],
        "metrics": None,
        "evidence": [{"ref_kind": "FILEPATH", "ref": str(path)}],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot-file", default=None, help="optional sentinel snapshot JSON path")
    ap.add_argument("--symbol", default=None, help="e.g., BTCUSDT")
    ap.add_argument("--timeframe", default="15m", help="1m|5m|15m|1h|4h|1d|other")
    ap.add_argument("--score", type=int, default=None, help="0..100")
    ap.add_argument("--confidence", type=float, default=None, help="0..1")
    ap.add_argument("--risk-level", choices=["low", "medium", "high"], default=None)
    ap.add_argument("--direction", choices=["long", "short", "neutral"])
    ap.add_argument("--tags", action="append", default=[], help="repeatable and/or comma-separated")
    ap.add_argument("--metrics-json", default=None, help="optional JSON object string")
    ap.add_argument(
        "--evidence",
        action="append",
        default=[],
        help='repeatable key=value pairs, e.g. "ref_kind=FILEPATH ref=/tmp/x.json"',
    )
    ap.add_argument("--ci", action="store_true", help="force deterministic timestamp")
    ap.add_argument("--out", required=True, help="output file path")
    args = ap.parse_args()

    if args.snapshot_file:
        snapshot_values = _from_snapshot(args.snapshot_file)
        symbol = snapshot_values["symbol"]
        timeframe = snapshot_values["timeframe"]
        score = snapshot_values["score"]
        confidence = snapshot_values["confidence"]
        risk_level = snapshot_values["risk_level"]
        direction = snapshot_values["direction"]
        tags = snapshot_values["tags"]
        metrics = snapshot_values["metrics"]
        evidence_refs = snapshot_values["evidence"]
    else:
        if args.symbol is None or args.score is None or args.confidence is None or args.risk_level is None:
            raise SystemExit(
                "FAIL-CLOSED: direct mode requires --symbol --score --confidence --risk-level"
            )
        symbol = args.symbol
        timeframe = args.timeframe
        score = args.score
        confidence = args.confidence
        risk_level = args.risk_level
        direction = args.direction
        tags = _parse_tags(args.tags)
        metrics = _parse_metrics(args.metrics_json)
        evidence_refs = _parse_evidence(args.evidence)

    if not 0 <= score <= 100:
        raise SystemExit("FAIL-CLOSED: --score must be in [0, 100]")
    if not 0 <= confidence <= 1:
        raise SystemExit("FAIL-CLOSED: --confidence must be in [0, 1]")

    deterministic = _deterministic_mode(args.ci)
    if deterministic:
        ts_iso = "1970-01-01T00:00:00Z"
        ts_for_id = 0
    else:
        now_utc = datetime.now(timezone.utc).replace(microsecond=0)
        ts_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        ts_for_id = int(time.time())

    signal = {
        "type": "BYBIT_ALERT",
        "symbol": symbol,
        "timeframe": timeframe,
        "score": score,
        "confidence": confidence,
        "risk_level": risk_level,
    }
    if direction:
        signal["direction"] = direction
    if tags:
        signal["tags"] = tags

    if metrics is not None:
        signal["metrics"] = metrics

    repo_root = _repo_root()
    build_sha = _build_sha(repo_root)

    event = {
        "schema": "domain_event.v1",
        "domain": "sentinel",
        "kind": "SIGNAL",
        "event_id": f"SENTINEL:SIGNAL:BYBIT_ALERT:{symbol}:{ts_for_id}:1",
        "ts_iso": ts_iso,
        "signal": signal,
        "meta": {
            "producer": "sentinel.social",
            "version": "v1",
            "build_sha": build_sha,
        },
    }

    if evidence_refs:
        event["evidence_refs"] = evidence_refs

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(event, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _validate_output(repo_root, out_path)
    print(f"OK: wrote+validated {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
