import hashlib
from pathlib import Path

# If contract files change, update the expected hashes intentionally in the same PR.
EXPECTED = {
    "engine_request_v1.json": "39f1dd99f1a1d183717f60bb3d6360bb49ba79b09ea2f7cc5cdd8bd6380022ba",
    "engine_result_v1.json": "39e0ed5cb3018d46241d3327743faa7dd96435d78635cd8d8af3f50205730cca",
    "adapter_contract_v1.json": "f401b368d83ecb084d03a29adb7c3fbd35bb6d9f0dfd7847c8adbea38ddeeef2",
}

def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def test_contract_hash_lock():
    base = Path("core/contracts")
    for name, expected in EXPECTED.items():
        p = base / name
        assert p.exists(), f"Missing contract: {p}"
        h = _sha256(p)
        assert expected is not None, f"Set expected hash for {name}: {h}"
        assert h == expected, f"Contract changed for {name}. expected={expected} actual={h}"
