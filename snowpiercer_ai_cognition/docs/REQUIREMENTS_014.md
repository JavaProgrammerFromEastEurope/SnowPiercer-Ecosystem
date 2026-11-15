# AI-CORE-014 — Requirements, contracts, safety and evidence

Status: PARTIAL. This Stage introduces a durable authenticated PREPARED/CLEAN phase journal and fail-closed production adapter. It does not claim atomic commit across SQLite and the checkpoint.

## Requirements
- R014-01: persist PREPARED intent before invoking admission.
- R014-02: persist CLEAN only after checkpoint verification.
- R014-03: reject admission on pending or corrupted journal.
- R014-04: require a one-time recovery permit when SQLite has advanced beyond checkpoint.
- R014-05: preserve all previous library APIs.

## Contract
`JournaledAdmissionGateway(gateway, journal, recovery_secret)` requires an existing anchored gateway, pre-provisioned journal, and 32+ byte secret. `admit()` returns the underlying gateway result; `verify()` rejects pending journal; `recover()` may clear PREPARED if SQLite and checkpoint have not advanced, otherwise requires a valid signed permit. Journal is protected by HMAC-SHA256 and durable replace/fsync, but must be kept under OS-enforced owner-only access. This adapter must be the only authorized production writer.

## Safety analysis
The phase journal is not an external monotonic trust root. Simultaneous rollback of SQLite, checkpoint and journal may evade detection. An attacker with filesystem write permissions can replace files, manipulate permissions or disable the adapter. Existing production013 service does not automatically instantiate this adapter: mandatory production write fencing across all entry points is NOT established. Journal updates and SQLite commit are separate durable domains; a crash leaves a detectable fenced state rather than a globally atomic commit. Real SIGKILL phase injection, cross-UID E2E recovery and socket-substitution testing for this new adapter have NOT been performed. The inherited earlier tests cover some of these categories but do not prove AI-CORE-014 end-to-end guarantees. Safety-critical readiness: NO-GO.

## Evidence
Three full pytest runs: 120 passed, 3 skipped, 26 subtests passed each, with ResourceWarning and DeprecationWarning treated as errors. New tests cover journal roundtrip, tampering, symlink rejection and missing journal. No full-stack fault-injection tests of the new adapter yet. See evidence/stage014_run{1,2,3}.txt.
