#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _now_ts_iso() -> str:
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
    final = _get_final(item)
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
    execution_mode: str,
    score: int,
    direction: str | None,
    risk_level: str,
    confidence: float,
    oi_delta_pct: float | None,
) -> tuple[bool, str]:
    # OI drop veto (percent units, eg -20 == -20%)
    if oi_delta_pct is not None and oi_delta_pct <= -20.0:
        return (False, "NO_TRADE_OI_DROP_VETO")

    if execution_mode == "paper":
        min_score = 60
        min_conf = 0.55
    else:
        min_score = 75
        min_conf = 0.70

    if (
        score >= min_score
        and direction in ("long", "short")
        and risk_level in ("low", "medium")
        and confidence >= min_conf
    ):
        return (True, "EXECUTE_CONDITIONS_MET")

    return (False, "NO_ACTION_CONDITIONS_NOT_MET")


def _default_quality_effects() -> dict:
    return {
        "size_multiplier": 1.0,
        "allow_new_entries": True,
        "reduce_only": False,
        "deny": False,
    }


def _extract_item_quality(item: dict) -> tuple[bool, str]:
    q = item.get("quality")
    if not isinstance(q, dict):
        return (False, "none")
    evidence_ok = bool(q.get("evidence_ok"))
    severity_max = q.get("severity_max")
    if severity_max not in ("none", "warn", "error"):
        severity_max = "none"
    return (evidence_ok, str(severity_max))


def _apply_effect_overrides(effects: dict, raw: Any) -> dict:
    if not isinstance(raw, dict):
        return effects
    out = dict(effects)

    mult = raw.get("size_multiplier")
    if isinstance(mult, (int, float)):
        out["size_multiplier"] = float(mult)

    allow = raw.get("allow_new_entries")
    if isinstance(allow, bool):
        out["allow_new_entries"] = allow

    reduce_only = raw.get("reduce_only")
    if isinstance(reduce_only, bool):
        out["reduce_only"] = reduce_only

    deny = raw.get("deny")
    if isinstance(deny, bool):
        out["deny"] = deny

    return out


def _apply_quality_policy(policy: dict, item: dict, triggered: bool, reason: str) -> tuple[bool, str, dict]:
    qp = policy.get("quality_policy")
    if not isinstance(qp, dict):
        raise ValueError("policy.quality_policy must be object")

    mode = qp.get("mode")
    if mode not in ("observer", "soft_gate", "hard_gate"):
        raise ValueError("policy.quality_policy.mode invalid")

    evidence_ok, severity_max = _extract_item_quality(item)
    effects = _default_quality_effects()

    out_triggered = bool(triggered)
    out_reason = str(reason)

    if mode == "soft_gate":
        soft = qp.get("soft_gate")
        if not isinstance(soft, dict):
            raise ValueError("policy.quality_policy.soft_gate must be object")
        if severity_max == "error" or not evidence_ok:
            effects = _apply_effect_overrides(effects, soft.get("error"))
        elif severity_max == "warn":
            effects = _apply_effect_overrides(effects, soft.get("warn"))

    elif mode == "hard_gate":
        hard = qp.get("hard_gate")
        if not isinstance(hard, dict):
            raise ValueError("policy.quality_policy.hard_gate must be object")
        deny_on = hard.get("deny_on")
        if not isinstance(deny_on, dict):
            raise ValueError("policy.quality_policy.hard_gate.deny_on must be object")

        deny = False
        if bool(deny_on.get("evidence_not_ok")) and not evidence_ok:
            deny = True
        if bool(deny_on.get("severity_error")) and severity_max == "error":
            deny = True

        if deny:
            out_triggered = False
            out_reason = "QUALITY_HARD_GATE_DENY"
            effects["size_multiplier"] = 0.0
            effects["allow_new_entries"] = False
            effects["reduce_only"] = True
            effects["deny"] = True

    quality = {
        "mode": mode,
        "evidence_ok": evidence_ok,
        "severity_max": severity_max,
        "effects": effects,
    }
    return out_triggered, out_reason, quality


def _policy_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_trigger_policy(path: Path) -> dict:
    obj = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("policy must be a YAML mapping")
    if obj.get("schema") != "sentinel_exec_trigger_policy.v1":
        raise ValueError("policy.schema mismatch")
    qp = obj.get("quality_policy")
    if not isinstance(qp, dict):
        raise ValueError("policy.quality_policy missing")
    mode = qp.get("mode")
    if mode not in ("observer", "soft_gate", "hard_gate"):
        raise ValueError("policy.quality_policy.mode invalid")
    return obj


def _compute_oi_delta_pct(symbol: str, ts: str, deriv_root: str = "/tmp/metaos_derivatives") -> float | None:
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
        with open(cur_path, "r", encoding="utf-8") as f:
            cur = json.load(f)
        with open(prev_path, "r", encoding="utf-8") as f:
            prev = json.load(f)
    except Exception:
        return None

    cur_oi = float(cur.get("derivatives", {}).get("open_interest", 0))
    prev_oi = float(prev.get("derivatives", {}).get("open_interest", 0))
    if prev_oi == 0:
        return None

    return (cur_oi - prev_oi) / prev_oi * 100.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-file", required=True)
    ap.add_argument("--outbox", required=True, help="directory to write intent JSON")
    ap.add_argument(
        "--policy-file",
        default="policies/sentinel/exec_trigger_v1.yaml",
        help="YAML trigger policy file",
    )
    ap.add_argument(
        "--policy-sha256",
        default=None,
        help="If set, fail-closed unless sha256(policy_file) matches",
    )
    ap.add_argument("--dry-run", type=int, default=1, help="1 = DRY_RUN (default), 0 = live intent")
    ap.add_argument("--execution-mode", choices=["dry_run", "paper", "live"], default=None)
    args = ap.parse_args()

    execution_mode = args.execution_mode if args.execution_mode else ("dry_run" if bool(int(args.dry_run)) else "paper")
    if execution_mode not in ("dry_run", "paper", "live"):
        raise ValueError(f"invalid execution_mode: {execution_mode}")

    policy_path = Path(args.policy_file)
    if not policy_path.is_file():
        raise ValueError(f"policy file not found: {policy_path}")

    policy_sha = _policy_sha256(policy_path)

    # FAIL-CLOSED, but only when caller provides expected sha (capsule lock).
    # Tests use tmp policy files and SHOULD NOT be forced to match repo policy sha.
    if args.policy_sha256 is not None:
        expected = str(args.policy_sha256).strip()
        if not re.fullmatch(r"[a-f0-9]{64}", expected):
            raise ValueError("policy-sha256 must be 64 hex chars")
        if policy_sha != expected:
            raise ValueError(f"policy sha256 mismatch: expected={expected} got={policy_sha}")

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

            oi_delta_pct = item.get("oi_delta_pct")
            if oi_delta_pct is not None and not isinstance(oi_delta_pct, (int, float)):
                raise ValueError(f"{symbol}: item.oi_delta_pct must be numeric when present")
            oi_delta_pct_v = float(oi_delta_pct) if oi_delta_pct is not None else _compute_oi_delta_pct(symbol, ts)

            score, direction, risk, conf, snap = _select_signal(item)

            triggered, reason = _evaluate_trigger(
                execution_mode=execution_mode,
                score=score,
                direction=direction,
                risk_level=risk,
                confidence=conf,
                oi_delta_pct=oi_delta_pct_v,
            )

            triggered, reason, quality = _apply_quality_policy(policy, item, triggered, reason)

            intents.append(
                {
                    "symbol": symbol,
                    "timeframe": item.get("timeframe"),
                    "final_score": score,
                    "final_direction": direction,
                    "final_risk_level": risk,
                    "final_confidence": conf,
                    "oi_delta_pct": oi_delta_pct_v,
                    "snapshot_path": snap,
                    "triggered": triggered,
                    "reason_code": reason,
                    "quality": quality,
                }
            )

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
            "evidence_refs": [{"ref_kind": "FILEPATH", "ref": str(summary_path)}],
        }

        out_path = outbox_dir / f"intent_{ts}.json"
        out_path.write_text(json.dumps(event, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"OK: wrote {out_path}")
        return 0

    except Exception as exc:
        print(f"FAIL-CLOSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
