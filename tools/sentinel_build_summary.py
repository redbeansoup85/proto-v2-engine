#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


TS_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z$")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _parse_symbols(raw: str) -> list[str]:
    parts = [item.strip() for item in raw.split(",")]
    symbols = [item for item in parts if item]
    if not symbols:
        raise ValueError("symbols must contain at least one symbol")
    if len(symbols) != len(set(symbols)):
        raise ValueError("symbols must not contain duplicates")
    return symbols


def _validate_domain_event(repo_root: Path, event_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(repo_root / "sdk" / "validate_domain_event.py"), str(event_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "unknown validation error"
        raise ValueError(f"domain_event invalid ({event_path}): {detail}")


def _build_sha(repo_root: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--verify", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        return "n/a"
    sha = proc.stdout.strip()
    return sha if re.fullmatch(r"[a-fA-F0-9]{7,64}", sha) else "n/a"


def _extract_snapshot_path(event: dict, symbol: str, ts: str) -> str:
    metrics = event.get("signal", {}).get("metrics")
    if isinstance(metrics, dict):
        snapshot_path = metrics.get("snapshot_path")
        if isinstance(snapshot_path, str) and snapshot_path:
            return snapshot_path

    evidence_refs = event.get("evidence_refs")
    if isinstance(evidence_refs, list):
        for ref in evidence_refs:
            if not isinstance(ref, dict):
                raise ValueError("evidence_refs entries must be objects")
            if ref.get("ref_kind") == "FILEPATH":
                candidate = ref.get("ref")
                if isinstance(candidate, str) and candidate:
                    return candidate

    return f"/tmp/metaos_snapshots/{symbol}/snapshot_{ts}.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ts", required=True, help="UTC yyyymmddTHHMMSSZ")
    ap.add_argument("--symbols", required=True, help="comma-separated symbols")
    ap.add_argument("--domain-root", default="/tmp/metaos_domain_events")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if not TS_RE.fullmatch(args.ts):
        print("FAIL-CLOSED: --ts must match yyyymmddTHHMMSSZ")
        return 1

    try:
        symbols = _parse_symbols(args.symbols)
        repo_root = _repo_root()
        items: list[dict] = []
        for symbol in symbols:
            event_path = Path(args.domain_root) / symbol / f"domain_event_{args.ts}.json"
            if not event_path.exists():
                raise ValueError(f"missing domain_event file: {event_path}")
            _validate_domain_event(repo_root, event_path)

            event = json.loads(event_path.read_text(encoding="utf-8"))
            signal = event.get("signal")
            if not isinstance(signal, dict):
                raise ValueError(f"signal must be object in {event_path}")

            item = {
                "symbol": signal.get("symbol"),
                "ts_iso": event.get("ts_iso"),
                "score": signal.get("score"),
                "direction": signal.get("direction"),
                "risk_level": signal.get("risk_level"),
                "confidence": signal.get("confidence"),
                "snapshot_path": _extract_snapshot_path(event, symbol, args.ts),
                "domain_event_path": str(event_path),
            }

            if item["symbol"] != symbol:
                raise ValueError(f"symbol mismatch in {event_path}: expected {symbol}, got {item['symbol']}")
            if not isinstance(item["ts_iso"], str) or not item["ts_iso"]:
                raise ValueError(f"invalid ts_iso in {event_path}")
            if not isinstance(item["score"], int):
                raise ValueError(f"invalid score in {event_path}")
            if item["direction"] not in (None, "long", "short", "neutral"):
                raise ValueError(f"invalid direction in {event_path}")
            if item["risk_level"] not in ("low", "medium", "high"):
                raise ValueError(f"invalid risk_level in {event_path}")
            if not isinstance(item["confidence"], (int, float)):
                raise ValueError(f"invalid confidence in {event_path}")
            if not isinstance(item["snapshot_path"], str) or not item["snapshot_path"]:
                raise ValueError(f"invalid snapshot_path in {event_path}")

            items.append(item)

        summary = {
            "schema": "sentinel_summary.v0",
            "ts": args.ts,
            "symbols": symbols,
            "items": items,
            "meta": {"build_sha": _build_sha(repo_root)},
        }
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"OK: wrote {out_path}")
        return 0
    except Exception as exc:
        print(f"FAIL-CLOSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
