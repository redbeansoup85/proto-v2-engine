"""
core.contracts package

This package co-exists with a legacy single-file module: core/contracts.py.
Many parts of the repo historically imported symbols via:

    from core.contracts import EngineInput, EngineOutput, ...

Python resolves 'core.contracts' to this package (core/contracts/__init__.py),
so we provide a compatibility re-export shim that loads core/contracts.py and
re-exports its public symbols.

LOCK intent:
- Keep runtime stable (no import-time breakage)
- Preserve existing import paths
- Allow gradual migration to package submodules later
"""

from __future__ import annotations

import sys as _sys
from importlib import util as _util
from pathlib import Path as _Path

# --- Load legacy module core/contracts.py (sibling of this package directory) ---
_legacy_path = _Path(__file__).resolve().parents[1] / "contracts.py"
if not _legacy_path.exists():
    raise ImportError(f"Legacy contracts module missing: {_legacy_path}")

# Use a stable module name and register it in sys.modules BEFORE exec_module
_modname = "core._contracts_legacy"
_spec = _util.spec_from_file_location(_modname, str(_legacy_path))
if _spec is None or _spec.loader is None:
    raise ImportError(f"Failed to load legacy contracts module: {_legacy_path}")

_legacy = _util.module_from_spec(_spec)
_sys.modules[_modname] = _legacy  # <-- critical for dataclasses / typing introspection
_spec.loader.exec_module(_legacy)  # type: ignore[assignment]

# --- Re-export commonly used legacy symbols (wide net; safe if absent) ---
_EXPORTS = [
    # engine IO / signals
    "EngineInput",
    "EngineOutput",
    "EngineDecision",
    "EngineSignal",
    "SignalType",
    "Severity",
    # meta / ids (if present)
    "EngineMeta",
    "DecisionMode",
    # any other commonly referenced contracts in repo
    "PolicyDecision",
]

for _name in _EXPORTS:
    if hasattr(_legacy, _name):
        globals()[_name] = getattr(_legacy, _name)

# Fallback: export any UpperCamelCase from legacy if needed (non-invasive)
for _name, _val in vars(_legacy).items():
    if _name and _name[0].isupper() and _name not in globals():
        globals()[_name] = _val

__all__ = [k for k in globals().keys() if k and k[0].isupper()]

# Contract enforcement errors
from .errors import (
    ContractViolationError,
    ContractExpiredError,
    ContractMalformedError,
    ContractForbiddenActionError,
    ContractConstraintError,
)
