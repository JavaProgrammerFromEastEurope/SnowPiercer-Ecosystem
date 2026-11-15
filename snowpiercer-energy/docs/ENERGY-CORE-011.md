# ENERGY-CORE-011 — Production Entry-Point Fencing & Durable Recovery Authorization

Status: PARTIAL / SAFETY BLOCKED / PHYSICAL NO-GO. Version 0.11.0.

## Requirements and evidence
- E011-R1: preserve all CORE-001..010 APIs: no existing source file removed; cumulative regression 139 tests.
- E011-R2: durable UID-bound single-use permits: `energy.production_v3.DurableEnergyService`; tests `test_production_v3.py`.
- E011-R3: permit consumption before recovery snapshot, transactionally in SQLite; fail-closed on missing database and invalid token.
- E011-R4: use existing unified advisory lock for permit issuance/consumption and gateway snapshot.
- E011-R5: globally eliminate legacy production bypass: BLOCKED; legacy `PersistentEnergyLedger.apply` and older servers remain callable.
- E011-R6: actual distinct OS UID end-to-end tests: NOT RUN.
- E011-R7: exhaustive SIGKILL at SQLite, phase journal, anchor and IPC boundaries: NOT RUN.
- E011-R8: independently protected anchor and durable permit DB: BLOCKED.

## Contract
`DurableEnergyService(admission, socket_path, allowed_uids, permit_db)` inherits the previous integrated service. `issue(uid)` returns `BrokerPermit`; `recover(uid, token)` consumes the permit durably before verifying ledger head. The socket retains `simulate`, `issue`, `recover` actions. UID at the IPC boundary is kernel-derived on Linux. The program is simulation-only.

## Architecture and threat model
Existing SQLite energy ledger and file-based anchor remain under the previous cooperative advisory lock. A second SQLite file stores permit tokens, UID, ledger sequence, digest and consumed flag. The permit DB is NOT cryptographically anchored. An attacker able to roll back or rewrite both databases and the anchor can defeat replay/rollback detection. Same-UID legacy direct API callers can bypass the new service. There is no physical hardware control.

## Safety assessment
Permit consumption is at-most-once under cooperative locking and normal SQLite commit semantics. A crash after consumption but before recovery verification can lose the permit: this is intentionally fail-closed. No guarantee is claimed for power loss, filesystem tampering, privileged attackers, noncooperating writers, or distinct-UID isolation. Production readiness: BLOCKED. Physical deployment: NO-GO.

## Regression evidence
Three successful full test runs recorded in `evidence/`: regression-1, regression-3, regression-4, each 139 PASS with ResourceWarning and DeprecationWarning escalated. A separate run regression-2 failed due to a BrokenPipeError race in a legacy IPC test; this flaky behavior is not resolved by this Stage. The successful runs do not eliminate that finding.
