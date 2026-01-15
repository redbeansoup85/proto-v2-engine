from __future__ import annotations

import pytest
from fastapi import HTTPException

from adapters.http.fastapi.policy_error_mapper import raise_http
from core.judgment.errors import conflict


def test_policy_error_to_http_exception():
    err = conflict("TEST_CONFLICT", "conflict happened", {"x": 1})

    with pytest.raises(HTTPException) as e:
        raise_http(err)

    exc = e.value
    assert exc.status_code == 409
    assert exc.detail["code"] == "TEST_CONFLICT"
    assert exc.detail["meta"]["x"] == 1
