from __future__ import annotations

from dataclasses import dataclass

from .mock_adapter import MockAdapter


class AdapterRegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class AdapterRegistry:
    def resolve(self, adapter_name: str | None):
        if not adapter_name:
            raise AdapterRegistryError("adapter_name is required (fail-closed)")

        normalized = str(adapter_name).strip().lower()
        if normalized in {"mock", "mock_adapter"}:
            return MockAdapter()

        raise AdapterRegistryError(f"unknown adapter: {adapter_name}")


def resolve_adapter(adapter_name: str | None):
    return AdapterRegistry().resolve(adapter_name)
