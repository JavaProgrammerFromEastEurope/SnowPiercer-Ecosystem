# TrainOS Stage 96 — Recovery journal commit failure safety

## Scope

Audit the trust boundary between publishing a verified recovery candidate and committing the recovery-attempt journal's terminal state.

## Change

`EventLogStartupRecovery.run()` no longer deletes the candidate by pathname when `finish_success()` fails. The candidate may have been replaced at that path by a competing process between publication and cleanup; an unconditional unlink could therefore delete a file this recovery call did not publish. Instead, the call returns `BLOCKED`, leaves the journal's `IN_PROGRESS` state intact, and preserves the candidate for the existing startup reconciliation path. That path independently verifies the checkpoint and candidate before it can mark the attempt successful.

## Tests

Added `tests/stage96/test_recovery_journal_commit_failure.py`:

1. Inject a journal completion failure after candidate publication; verify the call returns `BLOCKED`, preserves the candidate, and leaves the attempt `IN_PROGRESS`; then reopen the journal and verify safe reconciliation returns `RECOVERY_READY`.
2. Verify a trusted active log is accepted without touching a missing optional backup.
3. Simulate anchor-store unavailability and verify recovery fails closed without publishing a candidate.

## Validation

Validation results are recorded after running the focused and full test suites, compileall, AST parsing, and archive integrity checks.

## Limitations

These are software-level failure-injection tests, not physical power-loss tests. The candidate is not automatically promoted over the active database. Local SQLite journals and anchors are not tamper-proof external trust services, and this stage does not certify TrainOS for real train control.
