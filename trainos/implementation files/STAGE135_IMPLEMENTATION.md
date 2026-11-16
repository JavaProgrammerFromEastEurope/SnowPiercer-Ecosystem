# TrainOS Stage 135 — Recovery owner identity consistency

## Scope

Hardened decoding of active recovery journal rows so partially missing or malformed ownership metadata cannot be interpreted as an interrupted attempt and silently moved toward takeover.

## Changes

- Fenced `IN_PROGRESS` rows now require a non-empty run UUID, a positive integer owner PID, a positive fencing token, and a valid lease timestamp.
- A row without a run UUID is treated as legacy PID-only metadata only when its fencing token is zero; malformed non-null legacy PIDs are rejected.
- Corrupt ownership fields raise `RecoveryAttemptBlocked` and are not automatically repaired.
- Regression tests cover missing, zero, and negative owner PIDs, missing run identity with a modern fencing token, and continued readability of a legacy PID-only row.

## Safety boundary

This is local SQLite journal validation. PID liveness is only a same-host heuristic and does not provide distributed mutual exclusion, protection against PID reuse, or real-train safety certification.
