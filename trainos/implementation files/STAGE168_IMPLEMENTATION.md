# Stage 168 — inspection-time journal state changes

## Purpose

A read-only cross-journal inspection can otherwise return a report based on a
stale mixture of states if either SQLite journal changes while the inspection
is in progress. Because the idempotency ledger and execution audit are separate
databases, this stage does not claim to create a cross-database atomic snapshot.

## Changes

- `ExecutionJournalConsistencyChecker.inspect()` now re-reads the bound
  idempotency record and execution history after the initial consistency check.
- If the observed idempotency status or latest audit status changes during the
  inspection, it returns `RECONCILIATION_REQUIRED` and `may_dispatch` remains
  false.
- If either journal becomes unavailable during revalidation, it fails closed
  with `CONFLICT`.
- Added deterministic regression tests that introduce an idempotency transition
  and an audit transition during inspection.

## Limits

This revalidation detects changes observed during the inspection window; it is
not a distributed transaction or a lock spanning both databases. A caller must
revalidate at the dispatch boundary, and the external executor must provide its
own idempotency/fencing guarantees. This stage is not a safety certification.
