# ENERGY-CORE-007 — Unified Production Admission & Cross-UID Recovery Isolation

Version: v0.7.0. Scope: simulation-only, opt-in coordination. Deployment decision: BLOCKED / NO-GO.

## Requirements and contracts
- E007-R01: An opt-in controller serializes startup verification, simulation admission, and cold recovery with one advisory process lock.
- E007-R02: Lock file must be a private regular inode owned by effective UID, not a symlink or a replaced path.
- E007-R03: Recovery permits must be unpredictable, single-use, bound to the effective UID and ledger head; process-local storage prevents their transfer across restart.
- E007-R04: A controller inherited through fork must fail closed.
- E007-R05: Existing public APIs remain import-compatible and legacy unit tests must pass.
- E007-R06: Fault injection must cover critical commit boundaries; untested paths remain BLOCKED.

## Architecture
`UnifiedEnergyAdmission` wraps `TrustedEnergyGateway` (CORE-005) which wraps `PersistentEnergyLedger` (CORE-004). The advisory `flock` is taken before gateway's anchor lock and SQLite's BEGIN IMMEDIATE. Lock order: unified -> anchor -> SQLite. Cold recovery verifies the head and consumes the permit before verification; a failed recovery cannot replay the same permit.

## Safety analysis
- Legacy direct `PersistentEnergyLedger.apply()` bypasses the unified lock; a later gateway verification detects the divergent head but does not prevent the write. Mandatory production admission is BLOCKED.
- Anchor remains a mutable local file. Same-UID or privileged adversaries can tamper with anchor and DB; no independent trusted anchor is established.
- Recovery permit is not durable and does not enable genuine cross-UID recovery. Cross-UID E2E isolation BLOCKED.
- `flock` is advisory; lock replacement and namespace/file races require additional hardening.
- No real hardware commands, safety controller, independent electrical tests, or physical safety evidence exist. Physical deployment NO-GO.
- Tests use forced process exit (`os._exit`) at two SQLite/anchor boundaries; this is not equivalent to exhaustive SIGKILL coverage.

## Evidence
Three full pytest runs with ResourceWarning and DeprecationWarning treated as errors, third-party pytest plugin autoload disabled. See `evidence/energy-core-007-regression-{1,2,3}.txt`. Linux-only functionality requires separate portability assessment.

## Next stage
ENERGY-CORE-008 — Mandatory IPC Admission Consolidation & Exhaustive Crash-Point Verification.
