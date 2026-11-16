# ISLAND-GEO-013 architecture

Explicit crash hooks instrument the SQLite transaction boundaries and witness CAS in an opt-in subclass. The existing AnchoredAdmission and all legacy APIs are unchanged. The harness starts an independent witness process, kills service-worker processes with SIGKILL and attempts recovery. Witness database access must be controlled by a separate UID in production.

## Trust boundary
The test coordinator is privileged. A local witness SQLite file is not an independent tamper-proof anchor. Root can replace any file. The production service still has access to legacy library calls; OS-enforced legacy fencing remains unproven.

## Crash semantics
Before CAS: recovery may abort an uncommitted phase. After CAS: recovery may complete the matching phase. Any unexplained divergence denies recovery. The local SQLite DB and witness CAS are not one atomic transaction. No engineering approval is granted.
