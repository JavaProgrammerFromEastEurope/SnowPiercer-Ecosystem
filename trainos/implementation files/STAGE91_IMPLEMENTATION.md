# Stage 91 — Reconcile recovery publication after interruption

## Changes

- Added startup reconciliation for the crash window after a recovery candidate has been atomically published but before the durable attempt journal records `succeeded`.
- Reconciliation is attempted only when the durable journal says `in_progress` and the candidate path already exists.
- The checkpoint fingerprint must still match the interrupted attempt. The backup and candidate are independently assessed against the configured integrity anchor, and their event sequence and anchor sequence must match before the journal is completed.
- A candidate that is missing, untrusted, inconsistent with the checkpoint, or otherwise not reconcilable is left untouched and startup returns `BLOCKED`; it is not silently overwritten or promoted.
- Added tests that simulate abrupt termination using `SystemExit` immediately after candidate publication, close/reopen the attempt journal, and verify successful reconciliation on the next startup. Additional tests cover an invalid candidate and a changed checkpoint.

## Validation

- Focused tests for Stages 88–91: **18 passed**.
- Full test suite: **658 passed** in 4.09 seconds.
- `python -m compileall -q kernel tests`: passed.
- AST parse across `kernel` and `tests`: **2,570 Python files, 0 parse errors**.
- ZIP integrity: verified after packaging.

## Limitations

- The interruption test simulates abrupt termination at a controlled boundary; it is not a power-loss or filesystem durability certification test.
- Reconciliation relies on the configured integrity anchor and local SQLite journal. These application-level controls do not provide tamper-proof remote storage or independent hardware safety.
- Recovery candidates are prepared at a separate path; this component does not automatically replace the active event database or certify train-control use.
