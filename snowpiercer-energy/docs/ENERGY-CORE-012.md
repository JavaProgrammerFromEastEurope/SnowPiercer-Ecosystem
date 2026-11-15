# ENERGY-CORE-012 — Durable Permit Crash Consistency & Legacy IPC Race Elimination

## Requirements and acceptance
- R012-01: Retain prior public library API and all cumulative tests.
- R012-02: Gracefully handle disconnected legacy IPC clients without reapplying operations.
- R012-03: Atomically consume UID-bound permits before recovery verification; no replay after committed consume.
- R012-04: Verify crash before/after permit SQLite commit with independent subprocesses.
- R012-05: Verify concurrent consume single winner and corrupted permit DB rejection.
- R012-06: Three strict full regressions, warnings as errors.
- R012-07: Real cross-UID, malicious same-UID tampering, mandatory production fencing, all crash points: BLOCKED.

## Architecture and contract
Legacy EnergyIPCServer and IntegratedEnergyService retain their APIs. DurableEnergyService uses SQLite BEGIN IMMEDIATE and guarded UPDATE, commits permit consumption before recovery checks. Test-only ENERGY_TEST_CRASH_POINT injects immediate subprocess termination at permit_before_commit and permit_after_commit; never enable in deployment. UNIX socket responses handle client disconnect without retry.

## Safety analysis
- Permit consumed and response lost: retry denied, availability impact accepted.
- Crash before commit: SQLite rollback, permit remains valid.
- Crash after commit: permit remains consumed, replay denied.
- Full rollback of permit DB: not detectable with current local anchor; BLOCKED.
- Direct legacy ledger writes: still possible; mandatory fencing BLOCKED.
- Cross-UID isolation: no actual distinct-UID execution demonstrated; BLOCKED.
- SIGKILL matrix: tests use os._exit at two permit commit boundaries, NOT SIGKILL or exhaustive IPC/anchor/phase journal matrix.
- Hardware safety: NO-GO. No physical actuator control implemented.

## Evidence
See evidence/CORE-012-final-{1,2,3}.txt. Earlier failed tests and strict warning errors preserved in evidence/CORE-012-regression-*.txt and CORE-012-verified-1.txt. Three final strict regressions: 143 passed each. Warnings ResourceWarning, DeprecationWarning and PytestUnraisableExceptionWarning treated as errors. Third-party pytest plugin autoload disabled.

## Open risks
Untrusted file ownership and same-UID adversary, SQLite/anchor rollback, actual cross-UID authorization, complete SIGKILL crash point coverage, full production entry point fencing, physical and independent end-to-end certification.

## Readiness
Software regression PASS in tested environment; mandatory production safety BLOCKED; physical operation NO-GO.
