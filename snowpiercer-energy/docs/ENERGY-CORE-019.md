# ENERGY-CORE-019 — Cross-UID Production IPC End-to-End & Regression Deadlock Elimination

Version 0.19.0. Status: EXPERIMENTAL / BLOCKED / PHYSICAL NO-GO.

## Requirements and contracts

- R019-01: Linux kernel credentials must be used for peer identity; user-supplied UID is never authoritative. `authenticated_peer` denies unknown UID.
- R019-02: `bounded_accept` imposes a monotonic deadline on accepting a connection and raises `AcceptDeadlineExceeded`. Existing `serve_one` entry points remain backward compatible and do NOT yet use this deadline; this is a reusable opt-in primitive.
- R019-03: protected production files must be regular, owned by the dedicated non-root service UID, private, and not hardlinked. The opt-in preflight checks leaves, not an independently verified mount namespace.
- R019-04: diagnostic lock metadata must be read-only and must not imply ownership of a lock.
- R019-05: retain legacy library API; production deployment must deny legacy access to production state using OS permissions and independently configured identities.

## Architecture

`energy.ipc_diagnostics`: `bounded_accept(listener, timeout_s)`, `authenticated_peer(conn, allowed_uids)`, `assert_private_production_objects(paths, uid)`, `lock_diagnostics(path)`. This module is deliberately not a substitute for the `IsolatedProductionEnergyService` or for an independently provisioned witness.

## Safety analysis and verification evidence

- Five new targeted tests: bounded timeout, successful UNIX IPC and UID denial, root denial for private production object, diagnostic inode, and real root-spawned non-root UID UNIX IPC credential verification.
- Three full regressions: see `evidence/ENERGY-CORE-019-regression-{1,2,3}.txt`; each must be independently inspected for final pass status. `ResourceWarning` and `DeprecationWarning` are errors.
- Cross-UID E2E test covers kernel-authenticated socket connection but does **not** cover full production Energy simulate/issue/recover and separately administered witness. This requirement is BLOCKED.
- SIGKILL matrix across SQLite, phase journal, witness CAS and IPC: NOT executed; BLOCKED.
- Full rollback to genesis and coordinated ledger/permit/witness rollback: NOT independently verified; BLOCKED.
- Concurrent production startup, socket replacement and lock-file substitution: NOT exhaustively verified; BLOCKED.
- Global legacy production bypass closure: NOT achieved in library code; requires external OS isolation; BLOCKED.
- Regression deadlock elimination: not proven; bounded accept primitive alone does not cover all legacy blocking paths; BLOCKED.
- Independent witness trust root and attestation: not deployed; BLOCKED.

No physical energy control is implemented or authorized. Production readiness remains BLOCKED and physical deployment NO-GO.
