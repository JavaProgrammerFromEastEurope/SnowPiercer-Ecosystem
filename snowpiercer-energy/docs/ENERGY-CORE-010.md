# ENERGY-CORE-010 — Mandatory Recovery Broker Integration & Cross-UID End-to-End Verification

Version 0.10.0. Simulation only. Safety acceptance: BLOCKED; physical operation: NO-GO.

## Requirements and traceability

| ID | Requirement | Evidence | Decision |
|---|---|---|---|
| E010-R01 | Preserve CORE-001..009 library exports | cumulative pytest | PASS (tested) |
| E010-R02 | One IPC endpoint for simulate, issue and recover | test_production.py | PASS (opt-in endpoint) |
| E010-R03 | Authenticate UID from OS credentials | test_uid_denial; SO_PEERCRED | PASS same-UID/denied-list only |
| E010-R04 | Consume UID-bound permit once | test_combined_ipc_and_permits | PASS in-memory |
| E010-R05 | Fail closed on detectable unguarded ledger writes | test_anchor_missing_and_legacy_bypass | PASS for tested mismatch |
| E010-R06 | Enforce mandatory fencing on all legacy production APIs | none | BLOCKED |
| E010-R07 | Independent trusted anchor / genesis rollback detection | none | BLOCKED |
| E010-R08 | Real distinct-UID E2E | none | BLOCKED |
| E010-R09 | Exhaustive crash points SQLite/phase/anchor/IPC | prior partial tests only | BLOCKED |
| E010-R10 | Three full warning-strict regressions | evidence/ENERGY-CORE-010-regression-{1,2,3}.txt | PASS |

## Architecture / contracts

IntegratedEnergyService uses the CrossUIDRecoveryBroker socket lifecycle and UID check, and dispatches `simulate` via UnifiedEnergyAdmission.apply; `issue` and `recover` use the broker's one-shot in-memory permit table. All three actions are admitted only for allowlisted kernel peer UIDs. The interface accepts newline-delimited JSON up to MAX_REQUEST. Legacy public Python API exports remain available, therefore this is an opt-in simulated endpoint, not a mandatory global production fence.

Startup verifies the anchor before binding. `simulate` checks socket identity before admission. The existing gateway coordinates SQLite, phase-like pending anchor and commit using local advisory locks; no independent anchor trust root is provided. The new service does not add a durable phase journal.

## Safety and failure analysis

- Same-UID hostile actor can call direct PersistentEnergyLedger.apply or alter both SQLite and anchor: **BLOCKED**.
- Entire database and anchor rolled back to mutually consistent genesis: undetectable without independent monotonic root: **BLOCKED**.
- IPC socket substitution detected at tested points, but not proven against all races: **PARTIAL**.
- Cross-UID clients require OS-level account isolation and real tests; test suite checks only mocked/allowlist behavior: **BLOCKED**.
- Recovery permits are volatile; process restart loses permits. This is fail-denial but not durable recovery authorization.
- SIGKILL points previously tested are not exhaustive for the integrated service; no exhaustive claim.
- No hardware control, relay switching, battery management, or physical safety claims. **NO-GO**.

## Reproduction

`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -W error::ResourceWarning -W error::DeprecationWarning -m pytest -q`

The pytest suite uses installed pytest. Plugin autoload disabled to avoid unrelated environment warnings. Results are specific to this runtime, not independent certification.
