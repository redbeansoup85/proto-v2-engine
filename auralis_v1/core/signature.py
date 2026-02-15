from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class SignatureConfig:
    enabled: bool
    private_key_path: Optional[str]
    public_key_path: Optional[str]
    key_id: str
    algorithm: str


def _fail(code: str, detail: str = "") -> None:
    raise SystemExit(f"{code}: {detail}".strip(": "))


def _is_enabled(raw: Optional[str]) -> bool:
    return str(raw or "0").strip() == "1"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_private_key_hex(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except Exception as exc:
        _fail("SIG_PRIV_READ_FAIL", str(exc))


def load_sig_config_from_env() -> SignatureConfig:
    enabled = _is_enabled(os.getenv("SIG_ENABLED"))
    return SignatureConfig(
        enabled=enabled,
        private_key_path=os.getenv("SIG_PRIV"),
        public_key_path=os.getenv("SIG_PUB"),
        key_id=os.getenv("SIG_KEY_ID", "sentinel-node-01"),
        algorithm=os.getenv("SIG_ALG", "ed25519"),
    )


def sign_hash_hex(cfg: SignatureConfig, hash_hex: str) -> dict:
    if not cfg.enabled:
        return {}

    if cfg.algorithm != "ed25519":
        _fail("SIG_ALG_UNSUPPORTED", cfg.algorithm)

    if not cfg.private_key_path:
        _fail("SIG_PRIV_MISSING", "SIG_PRIV")

    try:
        digest = bytes.fromhex(hash_hex)
    except ValueError:
        _fail("SIG_BAD_HASH_HEX", hash_hex)

    try:
        from nacl.signing import SigningKey
    except Exception as exc:
        _fail("SIG_DEPENDENCY_MISSING", str(exc))

    private_hex = _load_private_key_hex(cfg.private_key_path)
    try:
        private_key_bytes = bytes.fromhex(private_hex)
        signer = SigningKey(private_key_bytes)
    except Exception as exc:
        _fail("SIG_PRIV_INVALID", str(exc))

    sig = signer.sign(digest).signature.hex()
    return {
        "algorithm": "ed25519",
        "key_id": cfg.key_id,
        "signature": sig,
        "signed_at": _utc_now_iso(),
        "signed_digest": "hash",
    }
