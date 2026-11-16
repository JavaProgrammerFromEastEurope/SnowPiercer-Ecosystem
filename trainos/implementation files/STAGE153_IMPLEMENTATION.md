# Stage 153 — Idempotency and execution identity binding

This stage binds an optional external `execution_id` to an idempotency key. The
SQLite schema is migrated additively for existing databases, and a partial unique
index prevents one execution identity from being claimed under two keys.

Completion and UNKNOWN-outcome reconciliation of a bound record require the same
execution identity. A different identity, omitted identity, or late attempt to bind
an older unbound record is rejected. This prevents a caller from resolving one
command through a mismatched execution reference.

The binding is application-level consistency, not a guarantee of exactly-once
external execution. The external executor must still enforce idempotency or expose
reliable reconciliation evidence.
