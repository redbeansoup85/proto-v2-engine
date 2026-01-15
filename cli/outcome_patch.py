from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import ulid

from vault.schemas_py.outcome import OutcomeRecord
from vault.schemas_py.registry import validate_schema


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


VAULT = repo_root() / "vault"


def read_json(p: Path) -> Dict[str, Any]:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json_atomic(p: Path, data: Dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def find_latest_complete(run_id: str) -> Optional[Dict[str, Any]]:
    idx = VAULT / "manifests" / "runs_index.jsonl"
    if not idx.exists():
        return None
    latest = None
    with open(idx, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("run_id") == run_id and obj.get("status") == "COMPLETE":
                latest = obj
    return latest


def append_patch_log(run_id: str, patch_id: str, outcome_path: Path, changes: Dict[str, Any]) -> Path:
    now = utc_now()
    dp = Path(now.strftime("%Y/%m/%d"))
    out = VAULT / "patches" / dp / f"patch_{patch_id}.json"

    patch_doc = {
        "schema": {"name": "card_patch", "version": "0.1.0"},
        "id": patch_id,
        "ts": now.isoformat().replace("+00:00", "Z"),
        "producer": {"system": "trading_os", "module": "outcome_patch", "instance": "sandbox-1"},
        "target": {"run_id": run_id, "outcome_path": str(outcome_path)},
        "changes": changes,
        "notes": "Outcome patch applied (A1 flow).",
    }
    write_json_atomic(out, patch_doc)
    return out


def main() -> int:
    p = argparse.ArgumentParser(prog="opatch", description="Patch OutcomeRecord after manual fills (A1 flow)")
    p.add_argument("--run-id", required=True)

    # pnl
    p.add_argument("--realized", type=float, required=True)
    p.add_argument("--unrealized", type=float, default=0.0)
    p.add_argument("--ccy", default="USDT")

    # excursions
    p.add_argument("--mae", type=float, default=0.0)
    p.add_argument("--mfe", type=float, default=0.0)

    # quality
    p.add_argument("--slippage", type=float, default=0.0)
    p.add_argument("--latency-ms", type=int, default=0)

    # labels
    p.add_argument("--result", default="WIN")  # WIN/LOSS/BREAKEVEN/OPEN/CANCEL
    p.add_argument("--reason", default="")

    # free notes
    p.add_argument("--notes", default="")

    args = p.parse_args()

    entry = find_latest_complete(args.run_id)
    if not entry:
        raise SystemExit(f"[ERROR] run_id not found/complete in runs_index: {args.run_id}")

    outcome_path = Path(entry["outcome_path"])
    if not outcome_path.exists():
        raise SystemExit(f"[ERROR] outcome file missing: {outcome_path}")

    old = read_json(outcome_path)

    # build new outcome (preserve id/ts/producer/run_id but refresh ts + fields)
    now = utc_now()
    new = OutcomeRecord(
        id=old.get("id", args.run_id),
        ts=now,
        producer=old.get("producer", {"system": "trading_os", "module": "logger", "instance": "sandbox-1"}),
        run_id=old.get("run_id", args.run_id),
        pnl={"realized": args.realized, "unrealized": args.unrealized, "ccy": args.ccy},
        excursions={"mae": args.mae, "mfe": args.mfe, "ccy": args.ccy},
        execution_quality={"slippage": args.slippage, "slippage_unit": "bps", "latency_ms": args.latency_ms},
        labels={"result": args.result, "reason": args.reason},
        notes=args.notes,
    )

    if not validate_schema(new.schema):
        raise SystemExit("[ERROR] invalid schema for OutcomeRecord")

    write_json_atomic(outcome_path, new.model_dump(mode="json"))

    patch_id = str(ulid.new())
    changes = {
        "pnl": new.pnl,
        "excursions": new.excursions,
        "execution_quality": new.execution_quality,
        "labels": new.labels,
        "notes": new.notes,
        "patched_at": now.isoformat().replace("+00:00", "Z"),
    }
    patch_path = append_patch_log(args.run_id, patch_id, outcome_path, changes)

    print(f"[OK] outcome patched for run_id={args.run_id}")
    print(f"  outcome: {outcome_path}")
    print(f"  patch:   {patch_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
