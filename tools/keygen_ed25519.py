#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _fail(code: str, detail: str = "") -> None:
    print(f"{code}: {detail}".strip(": "), file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate ed25519 keypair for Sentinel signing.")
    ap.add_argument("--out-dir", default="keys")
    ap.add_argument("--name", default="sentinel-node-01")
    args = ap.parse_args()

    try:
        from nacl.signing import SigningKey
    except Exception as exc:
        _fail("SIG_DEPENDENCY_MISSING", str(exc))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    priv_path = out_dir / f"{args.name}.private"
    pub_path = out_dir / f"{args.name}.public"

    signing_key = SigningKey.generate()
    verify_key = signing_key.verify_key

    priv_path.write_text(signing_key.encode().hex() + "\n", encoding="utf-8")
    pub_path.write_text(verify_key.encode().hex() + "\n", encoding="utf-8")

    try:
        os.chmod(priv_path, 0o600)
    except Exception:
        pass

    print(f"Wrote private key: {priv_path}")
    print(f"Wrote public key:  {pub_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
