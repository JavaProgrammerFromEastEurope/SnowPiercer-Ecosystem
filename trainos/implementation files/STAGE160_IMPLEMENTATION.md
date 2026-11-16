# Stage 160 — concurrent reconciliation and retry after restart

Added process-level tests for the race between reconciliation of an UNKNOWN external outcome and a retrying caller that reopens the idempotency ledger. The retrying caller must observe the existing record and must not create a new claim. Depending on transaction ordering, it can observe UNKNOWN or COMPLETED; the durable final state must be COMPLETED with the reconciled result and one audit entry.

A second test verifies that a completed record survives closing/reopening the SQLite store and a repeated claim returns the existing result rather than creating another record.

These tests validate local SQLite application-ledger semantics only. They do not prove exactly-once execution by arbitrary external systems or certify TrainOS for real train control.
