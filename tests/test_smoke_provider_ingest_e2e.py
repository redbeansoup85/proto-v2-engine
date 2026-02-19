from __future__ import annotations

from tools.smoke.smoke_provider_ingest import main


def test_smoke_provider_ingest_e2e(tmp_path) -> None:
    exceptions_dir = tmp_path / "Exceptions"
    rc = main(str(exceptions_dir))
    assert rc == 0
