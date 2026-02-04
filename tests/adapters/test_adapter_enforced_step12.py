import yaml
from pathlib import Path

def test_step12_contract_file_exists_and_parseable():
    path = Path("core/execution/contracts/step12_adapter_plan.yaml")
    assert path.exists(), "Step12 contract file is missing"
    data = yaml.safe_load(path.read_text())
    assert data.get("version") == "v1"
    assert "adapters" in data
    for row in data["adapters"]:
        for key in ("adapter_name", "enforcement_mode", "side_effects_allowed"):
            assert key in row
