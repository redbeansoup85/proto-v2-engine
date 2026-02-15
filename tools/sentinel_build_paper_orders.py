#!/usr/bin/env python3

import argparse, json, hashlib, yaml
from pathlib import Path
from datetime import datetime, timezone

def _canon(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def _sha256_hex(b: bytes) -> str:
    import hashlib
    return hashlib.sha256(b).hexdigest()

def _load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def _policy_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _load_policy(path: Path) -> dict:
    obj = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("policy must be YAML mapping")
    if obj.get("schema") != "sentinel_paper_orders_policy.v1":
        raise ValueError("policy.schema mismatch")
    return obj


def _quality_effects(item: dict) -> dict:
    q = item.get("quality")
    if not isinstance(q, dict):
        raise ValueError(f"invalid quality block for symbol={item.get('symbol')}")
    eff = q.get("effects")
    if not isinstance(eff, dict):
        raise ValueError(f"invalid quality.effects for symbol={item.get('symbol')}")

    size_multiplier = eff.get("size_multiplier")
    if not isinstance(size_multiplier, (int, float)) or float(size_multiplier) <= 0:
        raise ValueError(f"invalid quality.effects.size_multiplier for symbol={item.get('symbol')}")

    reduce_only = eff.get("reduce_only")
    if not isinstance(reduce_only, bool):
        raise ValueError(f"invalid quality.effects.reduce_only for symbol={item.get('symbol')}")

    # Backward-compatible acceptance: legacy allow_new_entries or canonical new_entries_allowed.
    new_entries_allowed = eff.get("new_entries_allowed")
    if new_entries_allowed is None:
        new_entries_allowed = eff.get("allow_new_entries")
    if not isinstance(new_entries_allowed, bool):
        raise ValueError(f"invalid quality.effects.new_entries_allowed for symbol={item.get('symbol')}")

    deny = eff.get("deny")
    if not isinstance(deny, bool):
        raise ValueError(f"invalid quality.effects.deny for symbol={item.get('symbol')}")

    return {
        "mode": q.get("mode"),
        "severity_max": q.get("severity_max"),
        "effects": {
            "size_multiplier": float(size_multiplier),
            "reduce_only": reduce_only,
            "new_entries_allowed": new_entries_allowed,
            "deny": deny,
        },
    }

def _match(rule_when: dict, ctx: dict) -> bool:
    # minimal matcher for v0
    def in_list(key, val):
        xs = rule_when.get(key)
        return (xs is None) or (val in xs)

    def gte(key, val):
        thr = rule_when.get(key)
        return (thr is None) or (val is not None and val >= thr)

    def gt(key, val):
        thr = rule_when.get(key)
        return (thr is None) or (val is not None and val > thr)

    return (
        in_list("execution_mode_in", ctx["execution_mode"]) and
        (rule_when.get("triggered_is") is None or ctx["triggered"] == rule_when["triggered_is"]) and
        in_list("direction_in", ctx["direction"]) and
        in_list("risk_level_in", ctx["risk_level"]) and
        gte("confidence_gte", ctx["confidence"]) and
        gte("score_gte", ctx["score"]) and
        gt("oi_delta_pct_gt", ctx["oi_delta_pct"])
    )

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execution-intent", required=True)
    ap.add_argument("--outbox", required=True)
    ap.add_argument("--policy-file", required=True)
    ap.add_argument("--policy-sha256", required=True)
    args = ap.parse_args()

    intent_path = Path(args.execution_intent)
    outbox_dir = Path(args.outbox)
    policy_path = Path(args.policy_file)

    if not intent_path.is_file():
        raise ValueError(f"execution intent not found: {intent_path}")
    if not policy_path.is_file():
        raise ValueError(f"policy not found: {policy_path}")

    sha = _policy_sha256(policy_path)
    if sha != args.policy_sha256:
        raise ValueError(f"policy sha256 mismatch expected={args.policy_sha256} got={sha}")

    policy = _load_policy(policy_path)
    outbox_dir.mkdir(parents=True, exist_ok=True)

    ei = _load_json(intent_path)
    if ei.get("schema") != "execution_intent.v1":
        raise ValueError("execution_intent schema mismatch")

    ts = ei.get("intent", {}).get("ts")
    execution_mode = ei.get("intent", {}).get("execution_mode", "dry_run")
    items = ei.get("intent", {}).get("items", [])
    if not isinstance(items, list):
        raise ValueError("intent.items must be list")

    defaults = policy.get("defaults", {})
    rules = sorted(policy.get("rules", []), key=lambda r: int(r.get("priority", 9999)))

    orders = []
    for it in items:
        ctx = {
            "execution_mode": execution_mode,
            "triggered": bool(it.get("triggered")),
            "direction": it.get("final_direction"),
            "risk_level": it.get("final_risk_level"),
            "confidence": float(it.get("final_confidence")),
            "score": float(it.get("final_score")),
            "oi_delta_pct": it.get("oi_delta_pct"),
        }

        emit = "NO_ORDER"
        rule_id = None
        for r in rules:
            when = r.get("when", {})
            action = r.get("action", {})
            if isinstance(when, dict) and isinstance(action, dict) and _match(when, ctx):
                emit = action.get("emit", "NO_ORDER")
                rule_id = r.get("id")
                break

        if emit == "PAPER_ORDER":
            quality = _quality_effects(it)
            effects = quality["effects"]
            if effects["deny"]:
                continue
            if not effects["new_entries_allowed"]:
                continue

            sizing = defaults.get("sizing")
            if not isinstance(sizing, dict):
                raise ValueError("policy.defaults.sizing must be object")
            base_size = sizing.get("equity_pct")
            if not isinstance(base_size, (int, float)) or float(base_size) <= 0:
                raise ValueError("policy.defaults.sizing.equity_pct must be > 0 numeric")
            applied_size = float(base_size) * float(effects["size_multiplier"])
            if not (applied_size > 0):
                continue

            orders.append({
                "symbol": it["symbol"],
                "side": "BUY" if ctx["direction"] == "long" else "SELL",
                "venue": defaults.get("venue"),
                "product": defaults.get("product"),
                "leverage": defaults.get("leverage"),
                "sizing": {**sizing, "equity_pct": applied_size},
                "sl": defaults.get("sl"),
                "tp": defaults.get("tp"),
                "quality": quality,
                "order_meta": {
                    "size_multiplier_applied": float(effects["size_multiplier"]),
                    "reduce_only": bool(effects["reduce_only"]),
                    "new_entries_allowed": bool(effects["new_entries_allowed"]),
                },
                "source": {
                    "execution_intent_event_id": ei.get("event_id"),
                    "rule_id": rule_id,
                }
            })

    out = {
        "schema": "paper_order_intent.v1",
        "domain": "SENTINEL_EXEC",
        "kind": "INTENT",
        "event_id": f"paper_{ts}",
        "ts_iso": _now_iso(),
        "intent": {
            "ts": ts,
            "execution_mode": execution_mode,
            "orders": orders,
        },
        "meta": {
            "producer": "sentinel.orders",
            "version": "0",
            "policy_id": policy.get("policy_id"),
            "policy_version": policy.get("version"),
            "policy_sha256": sha,
        },
        "evidence_refs": [
            {"ref_kind": "FILEPATH", "ref": str(intent_path)},
        ],
    }

    out_path = outbox_dir / f"paper_{ts}.json"
    out_path.write_bytes(_canon(out) + b"\n")
    print(f"OK: wrote {out_path} orders={len(orders)} mode={execution_mode}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
