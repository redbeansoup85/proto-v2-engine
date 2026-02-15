from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

from nacl.signing import SigningKey

_RE_HASH = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class SignatureConfig:
    enabled: bool
    priv_path: str
    key_id: str
    algorithm: str = "ed25519"

    @classmethod
    def from_mapping(cls, obj: Dict[str, Any]) -> "SignatureConfig":
        return cls(
            enabled=bool(obj.get("enabled", False)),
            priv_path=str(obj.get("priv_path") or obj.get("priv") or ""),
            key_id=str(obj.get("key_id") or ""),
            algorithm=str(obj.get("algorithm") or "ed25519"),
        )


def load_sig_config_from_env() -> SignatureConfig:
    enabled = os.getenv("SIG_ENABLED", "0").strip() == "1"
    return SignatureConfig(
        enabled=enabled,
        priv_path=os.getenv("SIG_PRIV", "").strip(),
        key_id=os.getenv("SIG_KEY_ID", "").strip(),
        algorithm=os.getenv("SIG_ALGO", "ed25519").strip() or "ed25519",
    )


def _coerce_cfg(cfg_like: Any) -> SignatureConfig:
    if isinstance(cfg_like, SignatureConfig):
        return cfg_like
    if isinstance(cfg_like, dict):
        return SignatureConfig.from_mapping(cfg_like)
    raise SystemExit(f"SIG_CFG_INVALID: {type(cfg_like).__name__}")


def _split_args(a: Any, b: Any) -> Tuple[SignatureConfig, str]:
    # Compatible with both call styles:
    #   sign_hash_hex(cfg, hash_hex)
    #   sign_hash_hex(hash_hex, cfg)
    if isinstance(a, SignatureConfig):
        return a, str(b)
    if isinstance(b, SignatureConfig):
        return b, str(a)

    if isinstance(a, dict) and isinstance(b, str):
        return _coerce_cfg(a), b
    if isinstance(b, dict) and isinstance(a, str):
        return _coerce_cfg(b), a

    raise SystemExit("SIG_CALL_INVALID: expected (cfg, hash_hex) or (hash_hex, cfg)")


def _load_signing_key(priv_path: str) -> SigningKey:
    if not priv_path:
        raise SystemExit("SIG_PRIV_MISSING: SIG_PRIV")
    p = Path(priv_path).expanduser()
    if not p.exists():
        raise SystemExit(f"SIG_PRIV_NOT_FOUND: {p}")

    raw = p.read_bytes()
    if len(raw) == 32:
        return SigningKey(raw)
    if len(raw) == 64:
        return SigningKey(raw[:32])

    txt = raw.decode("utf-8", errors="ignore").strip()
    if re.fullmatch(r"[0-9a-fA-F]{64}", txt):
        return SigningKey(bytes.fromhex(txt))
    if re.fullmatch(r"[0-9a-fA-F]{128}", txt):
        return SigningKey(bytes.fromhex(txt[:64]))

    raise SystemExit(f"SIG_PRIV_BAD_FORMAT: bytes={len(raw)}")


def sign_hash_hex(a: Any, b: Any) -> Dict[str, Any]:
    cfg, hash_hex = _split_args(a, b)

    if not cfg.enabled:
        return {}
    if not cfg.key_id:
        raise SystemExit("SIG_KEY_ID_MISSING: SIG_KEY_ID")
    if cfg.algorithm != "ed25519":
        raise SystemExit(f"SIG_ALGO_UNSUPPORTED: {cfg.algorithm}")
    if not isinstance(hash_hex, str) or not _RE_HASH.fullmatch(hash_hex):
        raise SystemExit("SIG_HASH_INVALID: expected 64-hex digest")

    signing_key = _load_signing_key(cfg.priv_path)
    sig_hex = signing_key.sign(bytes.fromhex(hash_hex)).signature.hex()
    return {
        "signature": sig_hex,
        "algorithm": "ed25519",
        "key_id": cfg.key_id,
        "signed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "signed_digest": "hash",
    }
