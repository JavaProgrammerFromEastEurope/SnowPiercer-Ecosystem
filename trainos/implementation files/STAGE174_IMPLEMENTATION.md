# Stage 174 — reconciliation evidence bound to dispatch generation

This stage closes a stale-evidence gap across a new dispatch attempt after an explicit `not_executed` decision.

- Adds a durable `dispatch_generation` counter to each idempotency record. Every successful reservation increments the counter.
- Records the generation alongside each `not_executed` reconciliation decision.
- Rejects evidence already used for an earlier generation when a later dispatch has happened.
- Allows fresh evidence for the current generation while preserving earlier evidence history.
- Migrates existing databases, treating a legacy row with `dispatch_started=1` as at least generation 1.
- Regression tests cover restart after re-reservation, replay blocking, stale-evidence rejection, fresh-evidence acceptance, and durable history.

The generation counter prevents local evidence from being silently reused across attempts; it does not validate the truth or authenticity of external evidence and does not make SQLite atomic with an external side effect.
