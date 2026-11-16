# Stage 232 — Financial ledger contract regression

## Scope

Adds a focused isolated-SQLite regression test for the command idempotency and reconciliation ledger. No external execution capability is added.

## Verification

The test exercises the behavior encoded in `tests/stage232/test_stage232_ledger_contract.py`, including state invariants, persistence, evidence freshness, identity binding, or cross-instance reservation as applicable.

## Safety boundary

Passing this local test does not authenticate external evidence, prove exactly-once physical execution, establish distributed consistency, or certify safety-critical deployment. Real payment integration remains NO-GO.
