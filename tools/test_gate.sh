#!/usr/bin/env bash
set -euo pipefail
export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///test.db}"
pytest -q tests/gates/test_required_checks_contract_gate.py
