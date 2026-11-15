# ENERGY-CORE-006 — IPC Admission and Trust Boundary
Status: simulation PASS, mandatory production BLOCKED, physical NO-GO.

## Requirements / traceability
- R006-01 Additive API preserving stages 001–005: all prior regression tests.
- R006-02 Kernel UID authentication using Linux SO_PEERCRED: tests/test_ipc.py.
- R006-03 Reject occupied socket path and unsafe directory: tests/test_ipc.py.
- R006-04 Verify anchor before socket publication: tests/test_ipc.py.
- R006-05 Reject hardware actions and replay: tests/test_ipc.py.
- R006-06 Three complete warning-strict regressions: evidence/energy-core-006-regression-{1,2,3}.txt.

## IPC contract
Newline-delimited JSON object with exactly action, operation_id, requests, duration_h, dispatch, reserve_kw, expected_sequence. Only action simulate is allowed. Response JSON contains ok and sequence/digest on success, error class on failure. Maximum request size 65536 bytes. UID is obtained from kernel, not caller-supplied JSON. Linux-only fail-closed on unsupported platforms.

## Architecture and safety analysis
Client -> UNIX socket -> kernel UID allowlist -> schema validation -> TrustedEnergyGateway -> SQLite ledger + local anchor. No physical actuator interface.

Threats tested: unauthorized allowlist UID (same-process synthetic test, NOT real second UID), socket occupation, missing anchor, replay, hardware action rejection. Prior stages test certain SIGKILL, rollback and concurrency cases; no new exhaustive SIGKILL sweep at IPC publication/accept/reply boundaries.

Residual risk / BLOCKED: anchor remains a same-host file, NOT independent root of trust. Existing direct PersistentEnergyLedger.apply remains accessible to preserve API compatibility; legacy bypass is NOT eliminated. No shared startup/recovery lock across socket publication and ledger transaction. Same-UID attacker, file/symlink races, coherent SQLite+anchor rollback to genesis, independent cross-UID e2e, socket replacement races, malicious owner, power loss and hardware control are NOT VERIFIED. No physical deployment permitted.
