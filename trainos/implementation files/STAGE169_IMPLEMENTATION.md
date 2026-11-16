# Stage 169 — Dispatch-boundary revalidation

This stage adds `ExecutionJournalConsistencyChecker.dispatch_if_consistent()`. It acquires the two store objects' in-process reentrant locks in a stable order, re-inspects the journals, and invokes the supplied callback only when the fresh report permits dispatch. A previously dispatchable inspection is not reused as authority.

`DispatchBoundaryResult` reports the fresh consistency report, whether the callback was invoked, and its return value. Non-dispatchable reports do not call the callback.

## Scope and limitations

The lock boundary applies only to callers sharing these exact store instances in one process. Separate processes, direct SQLite writers, crashes, and external side effects are not fenced or atomically committed by this method. A real dispatch adapter still needs downstream idempotency/fencing and explicit handling of uncertain outcomes. This is not safety certification or a guarantee of exactly-once physical execution.

## Tests

- A report that was consistent earlier is invalidated after the idempotency state changes to `UNKNOWN`.
- A same-process mutation using the shared store instance cannot interleave between final revalidation and callback exit.
- A non-dispatchable report never invokes the callback.
