# Submodule Hygiene & Static Scan Policy (LOCK-F4)

## Goal
Prevent CI drift / static-scan breakage caused by submodules, vendored trees, or fail-open exclusions.

## Rules (Fail-Closed)
1) Submodules are allowlist-only.
   - Any submodule path must exist in policies/submodules_allowlist.yaml.
   - URL and pinned commit must match allowlist.
   - Any git command failure = FAIL.

2) Static scan exclusions are allowlist-only.
   - Exclusions must match policies/static_scan_ignore_allowlist.yaml.
   - Broad excludes (** / / vendor/** / third_party/**) are forbidden.
   - Fail-open knobs (continue-on-error) are forbidden.
   - Parse/read failure = FAIL.

## Artifacts
- policies/submodules_allowlist.yaml
- policies/static_scan_ignore_allowlist.yaml
- tools/gates/submodule_hygiene_gate.py
- tools/gates/static_scan_policy_gate.py
