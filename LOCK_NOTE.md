
## CI Gate invariants (fail-closed)

- Template drift compares `.github/workflows` against `gatekit/templates` (single source of truth).
- Required checks contract is fail-closed:
  - workflow `name:` must be unique (avoid ambiguous check names)
  - gate job ids must be unique across workflows when required by contract checks
- Submodule hygiene is fail-closed: `vendor/gatekit` must remain pinned to the expected commit.
- Local repro: `./tools/local/run_ci_equivalent_gates.sh`
