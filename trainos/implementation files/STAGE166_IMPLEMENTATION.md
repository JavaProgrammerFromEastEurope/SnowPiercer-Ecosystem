# Stage 166 — Temporary journal unavailability and recovery

## Scope

This stage adds regression coverage for the diagnostic boundary when either SQLite journal becomes temporarily unavailable, then becomes available again after reopening.

## Behaviour covered

- A closed/unavailable audit-store connection produces a fail-closed `CONFLICT` report and never authorizes dispatch.
- Reopening the audit database permits a fresh read-only consistency check; a valid `CLAIMED` + `created` pair remains consistent.
- A closed idempotency-store connection likewise blocks dispatch.
- Reopening the idempotency database preserves `UNKNOWN` and continues to require explicit reconciliation.
- Diagnostics do not repair, mutate, or automatically replay either command.

## Validation

Run focused tests with `PYTHONPATH=. pytest -q tests/stage166 tests/stage165 tests/stage154` and the complete suite with `PYTHONPATH=. pytest -q`.

These are software regression tests, not proof of resilience against every storage failure and not railway safety certification.
