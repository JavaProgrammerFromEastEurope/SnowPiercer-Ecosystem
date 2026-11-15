# LIFE-CORE-009 — Trust architecture

The HMAC-SHA256 anchor is stored outside SQLite. A separately provisioned secret authenticates the anchor. SQLite configuration is inspected using the LIFE-CORE-008 guard verifier. Epoch floors detect database rollback **only after explicitly advancing the anchor**. Enrollment requires a valid fence and a v2-protected journal. All TrustedLifecycle writes/recovery verify the anchor.

## Threat boundaries

- An attacker controlling both anchor and key can forge anchors. No HSM, remote witness, or immutable store is included.
- Legacy HardenedLifecycle and direct SQLite access are not forcibly bound to the external anchor.
- This is not a globally monotonic transaction protocol. Advancing the anchor is explicit and non-atomic with DB changes; a crash can leave an out-of-date floor.
- Enrollment is opt-in. Missing anchor is fail-closed after enrollment for TrustedLifecycle, but a fresh TrustedLifecycle can still operate on an unanchored database for migration.
- HMAC integrity is not encryption; store secrets outside the project and outside the database.
- Do not use for control of life-support equipment.
