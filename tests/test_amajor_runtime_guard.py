from __future__ import annotations

from dataclasses import dataclass

import pytest

from core.engine.constitutional_transition import _enforce_amajor_requires_rationale


@dataclass
class _Approval:
    rationale_ref: str


def test_amajor_requires_rationale_ref_blocks_when_missing() -> None:
    with pytest.raises(PermissionError):
        _enforce_amajor_requires_rationale("A-MAJOR", _Approval(rationale_ref=""))


def test_amajor_allows_when_rationale_present() -> None:
    _enforce_amajor_requires_rationale("A-MAJOR", _Approval(rationale_ref="ui://constitutional/transition"))


def test_non_amajor_allows_missing_rationale_ref() -> None:
    _enforce_amajor_requires_rationale("A-MINOR", _Approval(rationale_ref=""))
    _enforce_amajor_requires_rationale("A-PATCH", _Approval(rationale_ref=""))
    _enforce_amajor_requires_rationale("", _Approval(rationale_ref=""))
