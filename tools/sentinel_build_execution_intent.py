#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import hashlib
import yaml
import glob
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _now_ts_iso() -> str:
    # UTC ISO-8601 seconds precision
    proc = subprocess.run(
        ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise ValueError("cannot compute ts_iso")
    return proc.stdout.strip()


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


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _get_final(item: dict) -> dict:
    """
    Prefer consensus output in item['final'].
    Fallback to item top-level fields (score/direction/risk_level/confidence) if needed.
    """
    f = item.get("final")
    if isinstance(f, dict):
        return f
    return {}


def _as_float(v: Any, name: str) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    raise ValueError(f"{name} must be numeric")


def _as_int(v: Any, name: str) -> int:
    if isinstance(v, int):
        return int(v)
    if isinstance(v, float) and float(v).is_integer():
        return int(v)
    raise ValueError(f"{name} must be int-like")


def _select_signal(item: dict) -> tuple[int, str | None, str, float, str | None]:
    """
    Returns: (score, direction, risk_level, confidence, snapshot_path)
    - direction can be None
    """
    final = _get_final(item)

    # consensus-first
    if final:
        score = _as_int(final.get("final_score"), "final.final_score")
        direction = final.get("final_direction")
        risk = final.get("final_risk_level")
        conf = _as_float(final.get("final_confidence"), "final.final_confidence")
        snap = final.get("final_snapshot_path")
        if direction not in (None, "long", "short", "neutral"):
            raise ValueError("final.final_direction invalid")
        if risk not in ("low", "medium", "high"):
            raise ValueError("final.final_risk_level invalid")
        if not isinstance(snap, str) or not snap:
            snap = None
        return score, direction, risk, conf, snap

    # raw fallback
    score = _as_int(item.get("score"), "item.score")
    direction = item.get("direction")
    risk = item.get("risk_level")
    conf = _as_float(item.get("confidence"), "item.confidence")
    snap = item.get("snapshot_path")
    if direction not in (None, "long", "short", "neutral"):
        raise ValueError("item.direction invalid")
    if risk not in ("low", "medium", "high"):
        raise ValueError("item.risk_level invalid")
    if not isinstance(snap, str) or not snap:
        snap = None
    return score, direction, risk, conf, snap


def _evaluate_trigger(
    *,
    score: int,
    direction: str | None,
    risk_level: str,
    confidence: float,
    oi_delta_pct: float | None,
) -> tuple[bool, str]:
    """
    Returns (triggered, reason_code).
    - reason_code is stable text for audit/filters.
    """
    # Safety veto
    if oi_delta_pct is not None and oi_delta_pct <= -0.20:
        return (False, "NO_TRADE_OI_DROP_VETO")

    if score >= 75 and direction in ("long", "short") and risk_level in ("low", "medium") and confidence >= 0.70:
        return (True, "EXECUTE_CONDITIONS_MET")

    return (False, "NO_ACTION_CONDITIONS_NOT_MET")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-file", required=True)
    ap.add_argument("--outbox", required=True, help="directory to write intent JSON")
    ap.add_argument("--policy-file", default="policies/sentinel/exec_trigger_v1.yaml", help="YAML trigger policy file")
    ap.add_argument("--policy-sha256", default=None, help="If set, fail-closed unless sha256(policy_file) matches")
    ap.add_argument("--dry-run", type=int, default=1, help="1 = DRY_RUN (default), 0 = live intent")
    ap.add_argument("--execution-mode", choices=["dry_run","paper","live"], default=None, help="Execution emission mode (SSOT). If omitted, derived from --dry-run for backward compatibility.")
    args = ap.parse_args()
    execution_mode = args.execution_mode if args.execution_mode else ("dry_run" if bool(int(args.dry_run)) else "paper")
    if execution_mode not in ("dry_run","paper","live"):
        raise ValueError(f"invalid execution_mode: {execution_mode}")
    
    policy_path = Path(args.policy_file)
    if not policy_path.is_file():
        raise ValueError(f"policy file not found: {policy_path}")
    policy_sha = _policy_sha256(policy_path)
    if args.policy_sha256 is not None and policy_sha != args.policy_sha256:
        raise ValueError(f"policy sha256 mismatch: expected={args.policy_sha256} got={policy_sha}")
    policy = _load_trigger_policy(policy_path)
    try:
        summary_path = Path(args.summary_file)
        outbox_dir = Path(args.outbox)
        outbox_dir.mkdir(parents=True, exist_ok=True)

        summary = _load_json(summary_path)
        items = summary.get("items")
        if not isinstance(items, list):
            raise ValueError("summary.items must be a list")

        ts = summary.get("ts")
        if not isinstance(ts, str) or not ts:
            raise ValueError("summary.ts must be non-empty string")

        repo_root = _repo_root()
        build_sha = _build_sha(repo_root)

        intents: list[dict] = []

        for item in items:
            if not isinstance(item, dict):
                raise ValueError("summary.items entries must be objects")

            symbol = item.get("symbol")
            if not isinstance(symbol, str) or not symbol:
                raise ValueError("item.symbol must be non-empty string")

            # optional - included by build_summary consensus path in your pipeline
            oi_delta_pct = item.get("oi_delta_pct")
            if oi_delta_pct is not None and not isinstance(oi_delta_pct, (int, float)):
                raise ValueError(f"{symbol}: item.oi_delta_pct must be numeric when present")
            oi_delta_pct_v = float(oi_delta_pct) if oi_delta_pct is not None else _compute_oi_delta_pct(symbol, ts)

            score, direction, risk, conf, snap = _select_signal(item)
            triggered, reason = _eval_trigger(policy, score=score, direction=direction, risk_level=risk, confidence=conf, oi_delta_pct=oi_delta_pct_v)
            intents.append(
                {
                    "symbol": symbol,
                    "timeframe": item.get("timeframe"),  # optional
                    "final_score": score,
                    "final_direction": direction,
                    "final_risk_level": risk,
                    "final_confidence": conf,
                    "oi_delta_pct": oi_delta_pct_v,
                    "snapshot_path": snap,
                    "triggered": triggered,
                    "reason_code": reason,
                }
            )

        # execution_intent.v1 envelope (fail-closed schema discipline)
        event = {
            "schema": "execution_intent.v1",
            "domain": "SENTINEL_EXEC",
            "kind": "INTENT",
            "event_id": f"intent_{ts}",
            "ts_iso": _now_ts_iso(),
            "intent": {
                "ts": ts,
                "execution_mode": execution_mode,
                "dry_run": (execution_mode == "dry_run"),
                "items": intents,
            },
            "meta": {
                "producer": "sentinel.exec",
                "version": "0",
                "build_sha": build_sha,
                "policy_id": policy.get("policy_id"),
                "policy_version": policy.get("version"),
                "policy_sha256": policy_sha,
            },
            "evidence_refs": [
                {
                    "ref_kind": "FILEPATH",
                    "ref": str(summary_path),
                }
            ],
        }

        out_path = outbox_dir / f"intent_{ts}.json"
        out_path.write_text(json.dumps(event, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"OK: wrote {out_path}")
        return 0

    except Exception as exc:
        print(f"FAIL-CLOSED: {exc}")
        return 1




def _policy_sha256(path: Path) -> str:
  return hashlib.sha256(path.read_bytes()).hexdigest()

def _load_trigger_policy(path: Path) -> dict:
  obj = yaml.safe_load(path.read_text(encoding="utf-8"))
  if not isinstance(obj, dict):
      raise ValueError("policy must be a YAML mapping")
  if obj.get("schema") != "sentinel_exec_trigger_policy.v1":
      raise ValueError("policy.schema mismatch")
  return obj

def _eval_trigger(policy: dict, *, score: float, direction: str | None, risk_level: str, confidence: float, oi_delta_pct: float | None) -> tuple[bool, str]:
  rules = policy.get("rules", [])
  if not isinstance(rules, list):
      raise ValueError("policy.rules must be list")

  rules_sorted = sorted(rules, key=lambda r: int(r.get("priority", 0)))

  for r in rules_sorted:
      when = r.get("when", {})
      action = r.get("action", {})
      if not isinstance(when, dict) or not isinstance(action, dict):
          continue

      ok = True
      if "oi_delta_pct_lte" in when:
          thr = float(when["oi_delta_pct_lte"])
          ok = ok and (oi_delta_pct is not None and float(oi_delta_pct) <= thr)

      if "score_gte" in when:
          ok = ok and (float(score) >= float(when["score_gte"]))

      if "direction_in" in when:
          ok = ok and (direction in list(when["direction_in"]))

      if "risk_level_in" in when:
          ok = ok and (risk_level in list(when["risk_level_in"]))

      if "confidence_gte" in when:
          ok = ok and (float(confidence) >= float(when["confidence_gte"]))

      if ok:
          return (bool(action.get("triggered")), str(action.get("reason_code", "POLICY_MATCH")))

  d = policy.get("default", {})
  return (bool(d.get("triggered", False)), str(d.get("reason_code", "NO_ACTION_CONDITIONS_NOT_MET")))

def _extract_open_interest(deriv_obj):
  try:
      return float(deriv_obj.get("derivatives", {}).get("open_interest"))
  except Exception:
      return None

def _compute_oi_delta_pct(symbol: str, ts: str, deriv_root: str = "/tmp/metaos_derivatives"):
  """
  Compute % change in OI between current deriv_<ts>.json and previous deriv_*.json.
  Returns float or None.
  """
  sym_dir = os.path.join(deriv_root, symbol)
  cur_path = os.path.join(sym_dir, f"deriv_{ts}.json")
  if not os.path.isfile(cur_path):
      return None

  files = sorted(glob.glob(os.path.join(sym_dir, "deriv_*.json")))
  if cur_path not in files:
      files = sorted(set(files + [cur_path]))

  idx = files.index(cur_path)
  if idx == 0:
      return None

  prev_path = files[idx - 1]
  try:
      cur = json.load(open(cur_path, "r", encoding="utf-8"))
      prev = json.load(open(prev_path, "r", encoding="utf-8"))
  except Exception:
      return None

  cur_oi = _extract_open_interest(cur)
  prev_oi = _extract_open_interest(prev)
  if cur_oi is None or prev_oi in (None, 0.0):
      return None

  return (cur_oi - prev_oi) / prev_oi * 100.0


if __name__ == "__main__":
    raise SystemExit(main())
