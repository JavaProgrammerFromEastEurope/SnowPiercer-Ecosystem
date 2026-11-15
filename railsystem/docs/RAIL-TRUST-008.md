# RAIL-TRUST-008 — Unified Admission Lifecycle & Crash-Recovery Evidence Closure

Status: PARTIAL / NO-GO. The implementation is a software prototype, not an independent safety case.

## Requirements and contracts
- R8-01: IPC startup must inspect the recovery fence under the shared admission.lock. Implemented in RAIL-TRUST-007.
- R8-02: IPC requests must revalidate the socket identity and recovery fence before entering the unified admission engine. Implemented; admission engine independently reacquires lock and validates state.
- R8-03: Unsupported legacy IPC commands must fail closed. Tested.
- R8-04: Teardown must not remove a socket path that was replaced. Tested.
- R8-05: Offline recovery and admission use the same lock. Existing API contract; not fully verified across UID boundaries.
- R8-06: Every crash boundary, rollback, replay, different UID, and external monotonic anchor must be verified end-to-end before production. OPEN.

## Safety analysis
The request preflight and admission are **not** a single lock transaction. The admission engine revalidates under its own lock; the preflight is advisory. The socket listener is not continuously holding the lifecycle lock. No trusted external monotonic provider is supplied. Cross-UID recovery and privilege separation are not implemented. A malicious privileged actor, filesystem rollback, or unexpected legacy entrypoint may bypass the assumptions. The absence of full fault-injection coverage is an open hazard.

## Evidence
Tests cover recovery activation after socket publication, rejection of a replaced socket path, and unsupported legacy IPC command rejection. Existing tests cover some lock and SIGKILL scenarios. These are not exhaustive fault injection or hardware tests. Release gate remains BLOCKED; physical operation NO-GO.
