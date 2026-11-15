# ENERGY-CORE-008 — Mandatory IPC Admission Consolidation & Crash-Point Verification

Version: 0.8.0. Scope: simulation-only; **production BLOCKED, physical NO-GO**.

## Requirements and traceability

- E008-R01: New IPC simulation writes MUST use UnifiedEnergyAdmission.apply; test_ipc_v2::test_mandatory_gateway_and_replay.
- E008-R02: New IPC MUST check Linux kernel peer UID against explicit allowlist; test_ipc_v2::test_denied_uid_and_hardware.
- E008-R03: New IPC MUST detect socket path substitution before request processing; test_ipc_v2::test_socket_substitution_fails_closed.
- E008-R04: New IPC MUST refuse startup on missing anchor; test_ipc_v2::test_missing_anchor_blocks_publication.
- E008-R05: New IPC MUST require unified admission and reject hardware actions; test_ipc_v2::test_requires_admission.
- E008-R06: Concurrent startup on one socket path MUST reject second binder; test_ipc_v2::test_concurrent_startup_one_socket_owner.
- E008-R07: Preserve legacy import and callable API; existing tests/test_ipc.py and previous suite.

## Architecture / contracts

`MandatoryEnergyIPCServer(admission, path, allowed_uids)` extends the legacy simulation-only server; its `serve_one()` authenticates peer UID, parses a bounded newline-delimited JSON envelope, and calls `admission.apply(...)`. The admission lock serializes participating writers and recovery operations. Socket directory must be private and owned by effective UID. `submit_simulation()` remains unchanged. The existing `EnergyIPCServer` is retained for library compatibility, but is not an authorized production endpoint.

Recovery permits remain process-local and effective-UID-bound in `UnifiedEnergyAdmission`; they are not cross-UID permits and do not provide persistent authorization. External anchor is an ordinary local file, not an independent trust root.

## Safety analysis

| Hazard | Mitigation | Residual risk |
| --- | --- | --- |
| Unauthorized simulation IPC | SO_PEERCRED allowlist | No demonstrated real cross-UID end-to-end isolation |
| Socket path replacement | inode/type/owner checks | TOCTOU after check, same-UID adversary |
| Duplicate operation | SQLite unique operation ID and admission | Direct legacy bypass possible |
| Ledger rollback | Compare external anchor | Coordinated rollback of both artifacts undetected |
| Crash at anchor/SQLite phase | Pending anchor recovery from CORE-005 | Power loss/fsync behavior not independently established |
| Concurrent startup | Private socket path and lock | Hostile same-UID processes not isolated |
| Physical actuation | No hardware API | No hardware safety validation |

## Evidence limits

The existing CORE-004 through CORE-007 tests exercise selected SIGKILL and corruption windows. This Stage does NOT claim exhaustive SIGKILL coverage of all IPC, SQLite, anchor and socket boundaries. Cross-UID tests with actual distinct OS identities were not executed. No independent root of trust, mandatory global legacy fencing, external security review, or physical end-to-end evidence exists. Therefore BLOCKED/NO-GO remains mandatory.
