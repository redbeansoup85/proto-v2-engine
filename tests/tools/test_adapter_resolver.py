from pathlib import Path
import pytest

from tools.adapters.adapter_resolver import resolve_adapter, AdapterResolutionError


def test_resolve_fails_when_card_not_registered():
    with pytest.raises(AdapterResolutionError):
        resolve_adapter(card_id="MISSING_V1", registry_path=Path("policies/adapter_registry.yaml"))
