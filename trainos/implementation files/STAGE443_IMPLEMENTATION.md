# Stage 443 — Reject impossible audit generations

## Scope

Injects a reconciliation row whose dispatch generation exceeds the command record generation and checks validation reports the inconsistency.

## Contract

Audit generation values must be non-negative and cannot exceed the associated command generation.

## Verification

Automated test: `tests/stage443/`. The release manifest records the aggregate targeted and regression test results.
