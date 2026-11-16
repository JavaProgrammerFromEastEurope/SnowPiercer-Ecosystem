# Stage 126 — Interrupted Attempt Reconciliation vs Retry Authorization

## Scope

Adds a multiprocessing regression test for the race between reconciling a crashed
`IN_PROGRESS` recovery attempt and a concurrent explicit `authorize_retry()` call.
Audit confirmed that interrupted-attempt reconciliation intentionally preserves the prior
`owner_run_id` as forensic metadata, while clearing the active PID and lease. The test
therefore checks that the old UUID remains non-authoritative: status is `FAILED`, and
only explicit authorization followed by a new begin can start another attempt. No
production code change was needed.

## Invariants covered

- A simulated dead owner is reconciled from `IN_PROGRESS` to `FAILED` before a retry can be authorized.
- Concurrent authorization either sees `IN_PROGRESS` and is blocked, or runs after reconciliation and is explicitly authorized from `FAILED`.
- The reconciliation path does not increment attempts or fencing tokens; it clears active PID/lease data while preserving the former run UUID for forensic traceability.
- Authorization metadata is absent when authorization was blocked, and complete when authorization succeeded.
- Exactly one authorized retry advances the attempt count to the configured maximum and increments the fencing token once.

## Validation

Results are recorded below after the focused and full test runs. This stage adds tests only; it does not certify the recovery journal or TrainOS for real hardware.

- Focused regression set (`stage126`, `stage125`, `stage124`, `stage123`): **6 passed**.
- Full test suite: **744 passed**.
- `python -m compileall -q kernel tests`: passed.
- AST audit: **2,604 Python files, 0 parse errors**.
- ZIP integrity and exclusion audit: verified during packaging.
