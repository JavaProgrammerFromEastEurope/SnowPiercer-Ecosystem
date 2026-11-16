# ISLAND-GEO-009 — Production admission facade

## Scope
The new `island.production_admission` service requires admission on **its own** AF_UNIX endpoint, verifies Linux SO_PEERCRED client UID, validates selected filesystem metadata, recovers before publishing the endpoint, and delegates to existing `AnchoredAdmission` + witness CAS. API compatibility is preserved.

## Trust boundaries and deployment assumptions
The service and witness must be deployed with **different operating-system UIDs**, separate writable directories, independent witness provisioning, and mandatory access controls. These properties were **not** independently exercised here. Running both processes as the same UID is not evidence of independent trust. The legacy Python API can still be invoked directly, so OS-enforced production fencing is **NOT IMPLEMENTED**. Checking path metadata does not prevent TOCTOU or descriptor-level substitution. The witness client does not authenticate the server's UID on connect; socket path owner checks are insufficient against replacement attacks.

## Crash consistency
Stage008 has phase/witness/local crash injection tests, but not an exhaustive SIGKILL matrix across SQLite, filesystem synchronization, socket publication, IPC responses, and UID boundaries. Existing witness storage is mutable; genesis rollback resistance requires a separately secured external anchor. Fail closed on missing witness, mismatch, unsupported platform, invalid UID, invalid payload, or ambiguous recovery.

## Evidence and readiness
Three complete unit-test regressions passed with ResourceWarning and DeprecationWarning treated as errors. Tests do not prove cross-UID isolation or physical engineering suitability. Production security remains BLOCKED; construction and operation remain BLOCKED/NO-GO.
