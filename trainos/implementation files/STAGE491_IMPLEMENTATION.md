# Stage 491 — Reject stale not-executed evidence reuse

## Implementation

The validator detects reuse of the same not-executed evidence at a later dispatch generation, which normal API reconciliation already prevents.

## Test coverage

A valid two-generation backup has the later evidence replaced with the earlier proof and must be rejected.

## Safety boundary

This stage validates local SQLite backup consistency. It does not prove off-host durability, distributed exactly-once execution, or external payment-provider safety.
