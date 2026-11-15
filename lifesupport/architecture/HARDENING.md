# LIFE-CORE-008 — Protected Storage Integrity & Admission Hardening

`HardenedLifecycle` extends the LIFE-CORE-007 admitted writer without removing the old APIs. It checks the canonical definitions of the three `events` guards, the `life_admission` configuration row and, for version 2, a SHA-256 configuration seal. Checks occur on opening the hardened API and before protected transitions/recovery. A shared v2 gate also runs before writes through the earlier `AdmittedLifecycle` API.

## Migration

Open a version-1 protected journal with `HardenedLifecycle`, acquire a valid fence token, then call `harden(token)`. Migration uses BEGIN IMMEDIATE, verifies journal replay, writes the seal and switches admission version to 2 in one transaction. `harden` is idempotent. Do not attempt to repair altered guards automatically: quarantine and investigate.

## Boundaries

Not a hostile administrator security boundary: an attacker who can edit SQLite schema and the seal can forge matching values. Direct SQL against unprotected databases is outside this opt-in design. Existing live connections using other APIs are not automatically upgraded; the version-2 gate is enforced for `AdmittedLifecycle.transition`, but other paths, including privileged SQLite access, require separate threat modelling. No hardware safety claims.
