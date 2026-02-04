import json
from pathlib import Path


def test_adapter_capabilities_v1_parseable_and_minimal_invariants() -> None:
    path = Path("core/contracts/adapter_capabilities_v1.json")
    assert path.exists(), "missing adapter_capabilities_v1.json"

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("version") == "v1"

    adapters = data.get("adapters")
    assert isinstance(adapters, list)

    for row in adapters:
        assert isinstance(row, dict)
        for key in ("adapter_name", "modes", "timeouts_ms", "side_effects"):
            assert key in row, f"missing key: {key}"

        assert isinstance(row["adapter_name"], str) and row["adapter_name"].strip()
        assert isinstance(row["modes"], list) and row["modes"]
        assert set(row["modes"]).issubset({"ok", "mismatch", "timeout", "ambiguous"})
        assert isinstance(row["timeouts_ms"], int) and row["timeouts_ms"] > 0

        # Step 2 contract: shadow declaration only
        assert row["side_effects"] is False
