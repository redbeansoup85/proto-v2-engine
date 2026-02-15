#!/usr/bin/env python3

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from nacl.signing import SigningKey


def _run_verify(path: Path, pub: Path, sig_required: bool) -> tuple[int, str]:
    env = dict(os.environ)
    env["SIG_REQUIRED"] = "1" if sig_required else "0"
    cmd = [sys.executable, "tools/audits/verify_observer_event_signatures.py", "--path", str(path), "--pub", str(pub)]
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out.strip()


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + "\n", encoding="utf-8")


def _hex_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _make_signed_row(sk: SigningKey) -> dict:
    h = _hex_hash("observer-signature-selftest")
    sig = sk.sign(bytes.fromhex(h)).signature.hex()
    return {
        "schema_version": "v1",
        "event_id": "OBS-TEST-1",
        "prev_hash": "0",
        "hash": h,
        "signature": {
            "signature": sig,
            "algorithm": "ed25519",
            "key_id": "selftest",
            "signed_at": "2026-01-01T00:00:00Z",
            "signed_digest": "hash",
        },
        "signature_meta": {"enabled": True, "reason": "SIG_OK", "key_id": "selftest"},
    }


def _tamper_hex_char(h: str) -> str:
    return ("0" if h[0] != "0" else "1") + h[1:]


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        sk = SigningKey.generate()
        pub = tdp / "pub.key"
        pub.write_bytes(bytes(sk.verify_key))

        # Disabled-style event: no signature, should pass when SIG_REQUIRED=0.
        no_sig = tdp / "observer_no_sig.jsonl"
        rows_no_sig = [{"schema_version": "v1", "event_id": "OBS-TEST-0", "prev_hash": "0", "hash": _hex_hash("no-sig")}]
        _write_jsonl(no_sig, rows_no_sig)
        rc, out = _run_verify(no_sig, pub, sig_required=False)
        if rc != 0:
            raise SystemExit(f"FAIL: unsigned observer should pass when SIG_REQUIRED=0\n{out}")

        # Same file should fail when SIG_REQUIRED=1.
        rc, _ = _run_verify(no_sig, pub, sig_required=True)
        if rc == 0:
            raise SystemExit("FAIL: unsigned observer should fail when SIG_REQUIRED=1")

        # Enabled-style event: valid signature should pass.
        signed = tdp / "observer_signed.jsonl"
        row_signed = _make_signed_row(sk)
        _write_jsonl(signed, [row_signed])
        rc, out = _run_verify(signed, pub, sig_required=True)
        if rc != 0:
            raise SystemExit(f"FAIL: signed observer should pass when SIG_REQUIRED=1\n{out}")

        # Tampered signature should fail.
        tampered = tdp / "observer_tampered_sig.jsonl"
        row_bad = json.loads(json.dumps(row_signed))
        row_bad["signature"]["signature"] = _tamper_hex_char(row_bad["signature"]["signature"])
        _write_jsonl(tampered, [row_bad])
        rc, _ = _run_verify(tampered, pub, sig_required=True)
        if rc == 0:
            raise SystemExit("FAIL: tampered signature should fail")

    print("SELFTEST_OK_OBSERVER_EVENT_SIGNATURES")


if __name__ == "__main__":
    main()
