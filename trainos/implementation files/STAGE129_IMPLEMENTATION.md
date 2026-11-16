# Stage 129 — Reconcile after a transient verification outage

## Scope

Added regression coverage for the ambiguous-commit path when the journal write is
actually durable, the driver then reports a lost COMMIT acknowledgement, and the
resolver's fresh connection is temporarily unable to open the journal. The caller
must receive the original commit exception rather than an unverified success.

## Cases covered

- A durable `finish_success()` remains `SUCCEEDED` after restart and cannot be
  applied a second time.
- A durable `authorize_retry()` remains `RETRY_AUTHORIZED` after restart, retains
  its operator/reason/checkpoint metadata, and cannot be authorized twice.
- The recovered authorization consumes exactly one attempt when `begin_attempt()`
  is subsequently called; attempt count and fencing token advance once, and the
  configured maximum is respected.

## Implementation decision

No production code change was necessary. The tests verify that the existing
fail-closed behavior (propagate the original exception if verification is unavailable)
can be reconciled safely by reopening the authoritative journal once it is available.

## Validation

See the Stage 129 completion report for the executed focused and full-suite results.
