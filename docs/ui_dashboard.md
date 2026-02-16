# UI Dashboard (Read-Only)

`apps/ui` provides a product-style observer dashboard for Sentinel runtime status.

## Consumed Endpoints

- `GET /api/intent/latest`
- `GET /api/audit/chain/status`
- `GET /api/executor/status`

## Notes

- Read-only only. No execution endpoint calls are made from this UI.
- Auto refresh every 5 seconds and manual refresh are both supported.
- Any fetch/parse error is rendered as `n/a` in the UI to avoid runtime crashes.

## Screenshot

- Placeholder: `docs/assets/ui-dashboard-placeholder.png`
