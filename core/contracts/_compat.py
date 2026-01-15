from __future__ import annotations

try:
    # Python 3.11+
    from enum import StrEnum as _StrEnum  # type: ignore
except Exception:
    # Python 3.9/3.10 fallback
    from enum import Enum

    class _StrEnum(str, Enum):
        """Fallback for enum.StrEnum (Python < 3.11)."""
        pass

StrEnum = _StrEnum
