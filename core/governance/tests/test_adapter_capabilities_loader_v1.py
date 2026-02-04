from core.adapters.capabilities import get_adapter_capability, load_adapter_capabilities_v1


def test_load_adapter_capabilities_v1_returns_dict() -> None:
    data = load_adapter_capabilities_v1()
    assert isinstance(data, dict)


def test_get_adapter_capability_mock_has_required_shape() -> None:
    row = get_adapter_capability("mock")
    assert isinstance(row, dict)
    for key in ("adapter_name", "modes", "timeouts_ms", "side_effects"):
        assert key in row

    assert isinstance(row["adapter_name"], str)
    assert isinstance(row["modes"], list)
    assert isinstance(row["timeouts_ms"], int)
    assert row["side_effects"] is False


def test_get_adapter_capability_unknown_returns_none() -> None:
    assert get_adapter_capability("unknown") is None
