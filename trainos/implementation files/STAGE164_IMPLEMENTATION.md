# TrainOS Stage 164 — Partial Audit Write Recovery

## Scope

This stage strengthens recovery behavior when an audit journal contains malformed progress data that may resemble a partially persisted transition.

## Changes

- Recovery skips a malformed execution row instead of aborting the entire multi-execution recovery pass.
- The suspect history is left unchanged for investigation; `verify_integrity()` remains the diagnostic path.
- Added regression tests for invalid progress counters, SQLite transaction rollback across store reopen, and unknown persisted states.

## Safety behavior

The recovery routine does not guess or repair the outcome of a damaged command and does not automatically replay it. SQLite rollback tests demonstrate transaction behavior in this test setup, not power-loss durability guarantees for every filesystem or hardware platform.
