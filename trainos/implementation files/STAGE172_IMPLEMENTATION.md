# TrainOS Stage 172 — Explicit unknown-outcome reconciliation

## Scope

Adds `CommandIdempotencyStore.reconcile_not_executed(...)` for an explicit,
evidence-backed decision that an operation with status `UNKNOWN` was not
accepted/executed by the external system. The decision is committed together
with a durable reconciliation audit event and resets the dispatch reservation
only as part of that explicit state transition.

The method requires non-empty evidence and, for bound commands, the original
`execution_id`. Repeating the same decision/evidence is idempotent while a new
dispatch has not been reserved. Conflicting evidence is rejected. The audit
schema is migrated additively with a `decision` column; legacy events default to
`completed`.

## Safety boundary

This API cannot establish that evidence is truthful. A caller must obtain proof
from a trustworthy external authority that the command was not accepted. A
missing acknowledgement, timeout, process restart, or absent local journal row
is not sufficient evidence. The downstream executor must independently support
idempotency/fencing for physical actions. TrainOS is not safety-certified.
