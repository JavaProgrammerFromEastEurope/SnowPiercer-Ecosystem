# ISLAND-GEO-018 — Production fencing verification layer

## Architecture

Retains v0.18.0 production and authority services. Adds a separate, backwards-compatible `production_guard` verifier for Unix socket ownership/inode and private storage. The checker is intentionally not represented as a mandatory production fence; integration and external validation are outstanding.

## Admission and recovery

Existing service requires state-bound permit at startup and reconciles local SQLite and witness. The new verifier rejects untrusted socket and storage metadata. Direct legacy writes remain possible for any process holding the service UID or root; the library cannot prevent that by itself.

## OS boundary

Linux DAC can deny client/witness UID access to service-owned mode 0600 SQLite files. The test suite covers unit checks, while exhaustive independent UID, replacement races and crash-point tests remain open. A root-owned sticky IPC namespace mitigates cross-UID unlink but does not establish end-to-end socket authenticity or defend against privileged actors.

## Recovery caveat

No new independent monotonic hardware anchor is implemented. Replacing both local and witness SQLite may evade detection. No new production-level SIGKILL matrix was executed in this stage.
