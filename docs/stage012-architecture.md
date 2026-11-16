# ISLAND-GEO-012 — deployment architecture

Three Linux UIDs: client -> admission -> witness. Service-owned SQLite lives in mode 0700 directory; witness-owned SQLite in separate 0700 directory. Socket directories allow traversal but no untrusted writes; socket files use mode 0660 and shared testing GID. No direct client access to service/witness DB. Existing legacy library entrypoints remain importable, so fencing is OS-permission-based only when correctly provisioned.

## Trust boundary limitations

Witness CAS is not an independently authenticated, immutable monotonic store. `PinnedWitnessClient` validates kernel peer UID but a privileged operator can replace witness storage. `AnchoredAdmission` has non-atomic local initialization across multiple startup processes and no full crash-injection hooks. This stage does not claim exhaustive crash proof or deployment certification.
