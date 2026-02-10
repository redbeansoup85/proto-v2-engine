# POLICY-SENTINEL-TRADE-INTENT-V1

## Contract
- Schema ID: `sentinel_trade_intent.v1`
- This intent is interpretation-only and MUST remain non-executable.

## Mandatory Constraints
- `no_execute` MUST always be `true`.
- `side` MUST be one of: `LONG`, `SHORT`, `FLAT`.

## MUST NOT List (forbidden keys at any depth)
- `execute`
- `order`
- `place_order`
- `broker`
- `trade`
- `qty`
- `size`
- `price`
- `sl`
- `tp`
- `leverage`
- `position`
- `approve`
- `reject`
- `commit`
- `api_key`
- `private_key`
- `seed_phrase`
- `mnemonic`
- `password`
- `secret`
- `token`

## Fail-Closed Rule
If any mandatory constraint is violated, validation MUST fail-closed and the intent MUST be rejected.
