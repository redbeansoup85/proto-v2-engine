from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
import uuid


DEFAULT_LEDGER = Path("data/judgments/judgment.v1.jsonl")


@dataclass(frozen=True)
class JudgmentV1:
    schema: str
    judgment_id: str
    created_at: str
    actor: str
    verdict: str
    reason: Optional[str] = None

    domain: Optional[str] = None
    symbol: Optional[str] = None
    side: Optional[str] = None

    policy_sha256: Optional[str] = None
    refs: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "schema": self.schema,
            "judgment_id": self.judgment_id,
            "created_at": self.created_at,
            "actor": self.actor,
            "verdict": self.verdict,
        }
        if self.reason is not None:
            d["reason"] = self.reason
        if self.domain is not None:
            d["domain"] = self.domain
        if self.symbol is not None:
            d["symbol"] = self.symbol
        if self.side is not None:
            d["side"] = self.side
        if self.policy_sha256 is not None:
            d["policy_sha256"] = self.policy_sha256
        if self.refs is not None:
            d["refs"] = self.refs
        if self.metrics is not None:
            d["metrics"] = self.metrics
        return d


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_judgment_id() -> str:
    return "JDG-" + uuid.uuid4().hex[:12]


def append_judgment(
    verdict: str,
    actor: str,
    *,
    reason: Optional[str] = None,
    domain: Optional[str] = None,
    symbol: Optional[str] = None,
    side: Optional[str] = None,
    policy_sha256: Optional[str] = None,
    refs: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, Any]] = None,
    ledger_path: Path = DEFAULT_LEDGER,
) -> Dict[str, Any]:
    """
    Append-only judgment ledger writer (jsonl).
    Fail-closed: raises on any IO/serialization error.
    """
    j = JudgmentV1(
        schema="judgment.v1",
        judgment_id=new_judgment_id(),
        created_at=now_utc_iso(),
        actor=actor,
        verdict=verdict,
        reason=reason,
        domain=domain,
        symbol=symbol,
        side=side,
        policy_sha256=policy_sha256,
        refs=refs,
        metrics=metrics,
    ).to_dict()

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(j, ensure_ascii=False, separators=(",", ":"))

    # atomic-ish append: open in append mode, single write
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

    return j


def main() -> None:
    # minimal CLI: primarily for smoke/testing/manual injections
    verdict = os.getenv("JDG_VERDICT", "INFO")
    actor = os.getenv("JDG_ACTOR", "local")
    reason = os.getenv("JDG_REASON")
    out = append_judgment(verdict=verdict, actor=actor, reason=reason)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
