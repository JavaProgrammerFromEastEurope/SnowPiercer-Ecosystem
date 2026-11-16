# TrainOS Stage 145 — Retry Authorization Integrity

## Scope

Harden the durable recovery-attempt journal so a `RETRY_AUTHORIZED` row cannot
be consumed when its operator identity, authorization reason, or optional
checkpoint fingerprint is missing or malformed.

## Changes

- `_from_row` validates authorization fields whenever the persisted status is
  `RETRY_AUTHORIZED`.
- Missing/blank operator or reason and blank non-null checkpoint fingerprints
  raise `RecoveryAttemptBlocked` before state transitions.
- Regression tests corrupt each field externally and verify reads/start attempts
  fail closed while the durable status, attempt count, and fencing token remain
  unchanged.
- Checkpoint mismatch regression verifies the one-shot authorization remains
  intact for the exact approved fingerprint and is consumed only on successful
  start with that fingerprint.

## Safety boundary

These are software journal-integrity tests. They do not establish fitness for
controlling physical train equipment or any safety certification.
