from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict

import ulid

from vault.schemas_py.execution import ExecutionLog  # LOCK2_ALLOW_EXEC
from vault.schemas_py.outcome import OutcomeRecord
from vault.schemas_py.registry import validate_schema


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def resolve_vault_root() -> Path:
    here = Path(__file__).resolve()
    repo_root = here.parents[1]  # proto-v2-engine
    return repo_root / "vault"


VAULT_ROOT = resolve_vault_root()


def date_path(ts: datetime) -> Path:
    return Path(ts.strftime("%Y/%m/%d"))


def write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def append_jsonl(path: Path, entry: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def append_index(run_id: str, status: str, exec_path: Path, outcome_path: Path, ts: datetime) -> None:
    idx = VAULT_ROOT / "manifests" / "runs_index.jsonl"
    entry = {
        "run_id": run_id,
        "status": status,
        "exec_path": str(exec_path),
        "outcome_path": str(outcome_path),
        "ts": ts.isoformat().replace("+00:00", "Z"),
    }
    append_jsonl(idx, entry)


def main() -> int:
    p = argparse.ArgumentParser(prog="trade_logger", description="Trading OS write-only logger (v0.1)")
    p.add_argument("--strategy-card-id", required=True)
    p.add_argument("--strategy-card-version", default="1.0.0")
    p.add_argument("--judgment-card-id", required=True)
    p.add_argument("--judgment-card-version", default="1.0.0")
    p.add_argument("--context-id", default="")
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--venue", default="binance")
    p.add_argument("--instrument-type", default="perp")
    p.add_argument("--side", default="LONG")
    p.add_argument("--planned-size", type=float, default=1.0)
    p.add_argument("--size-unit", default="contracts")
    p.add_argument("--risk-sl", type=float, default=0.0)
    p.add_argument("--risk-tp", default="[]")
    p.add_argument("--labels-result", default="OPEN")
    p.add_argument("--notes", default="")

    args = p.parse_args()

    (VAULT_ROOT / "manifests").mkdir(parents=True, exist_ok=True)
    (VAULT_ROOT / "manifests" / "runs_index.jsonl").touch(exist_ok=True)

    now = utc_now()
    run_id = str(ulid.new())

    try:
        tp = json.loads(args.risk_tp)
    except json.JSONDecodeError:
        tp = []

    producer = {"system": "trading_os", "module": "logger", "instance": "sandbox-1"}

    run_data = {
        "run_id": run_id,
        "strategy_card_id": args.strategy_card_id,
        "strategy_card_version": args.strategy_card_version,
        "judgment_card_id": args.judgment_card_id,
        "judgment_card_version": args.judgment_card_version,
        "context_id": args.context_id,
    }

    instrument = {"symbol": args.symbol, "venue": args.venue, "type": args.instrument_type}
    intent = {"side": args.side, "planned_size": args.planned_size, "size_unit": args.size_unit}
    risk = {"sl": args.risk_sl, "tp": tp, "invalidation": "none"}

    exec_log = ExecutionLog(
        id=run_id,
        ts=now,
        producer=producer,
        run=run_data,
        instrument=instrument,
        intent=intent,
        risk=risk,
    )
    if not validate_schema(exec_log.schema):
        raise ValueError("Invalid schema for ExecutionLog")

    outcome = OutcomeRecord(
        id=run_id,
        ts=now,
        producer=producer,
        run_id=run_id,
        pnl={"realized": 0.0, "unrealized": 0.0, "ccy": "USDT"},
        excursions={"mae": 0.0, "mfe": 0.0, "ccy": "USDT"},
        execution_quality={"slippage": 0.0, "slippage_unit": "bps", "latency_ms": 0},
        labels={"result": args.labels_result, "reason": ""},
        notes=args.notes,
    )
    if not validate_schema(outcome.schema):
        raise ValueError("Invalid schema for OutcomeRecord")

    dp = date_path(now)
    exec_path = VAULT_ROOT / "executions" / dp / f"exec_{run_id}.json"
    outcome_path = VAULT_ROOT / "outcomes" / dp / f"outcome_{run_id}.json"

    try:
        append_index(run_id, "PENDING", exec_path, outcome_path, now)
        write_json_atomic(exec_path, exec_log.model_dump(mode="json"))
        write_json_atomic(outcome_path, outcome.model_dump(mode="json"))
        append_index(run_id, "COMPLETE", exec_path, outcome_path, now)
        print(run_id)
        return 0
    except Exception as e:
        for pth in (exec_path, outcome_path):
            try:
                if pth.exists():
                    pth.unlink()
            except Exception:
                pass
        append_index(run_id, "FAILED", exec_path, outcome_path, now)
        raise RuntimeError(f"Logging failed, rolled back: {e}") from e


if __name__ == "__main__":
    raise SystemExit(main())
