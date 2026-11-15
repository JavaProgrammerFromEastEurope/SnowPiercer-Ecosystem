# RAIL-TRUST-003 — Independent Anti-Rollback Anchoring & Mandatory Recovery Isolation

## Scope and requirements
- RAIL-TRUST-003-R1: serialize local admission and recovery with an owner-private advisory flock.
- RAIL-TRUST-003-R2: reject mismatched SQLite and external anchor state; no automatic rollback or reinitialization.
- RAIL-TRUST-003-R3: write durable PREPARED phase before advancing external anchor; finalize SQLite after anchor fsync.
- RAIL-TRUST-003-R4: recovery requires an offline permit, consumes it once and only reconciles a precisely matching PREPARED transaction.
- RAIL-TRUST-003-R5: reject symlink anchor, unsafe ownership/mode and malformed state.

## Contract
`initialize(state_dir)` provisions a new 0700 owner-controlled directory. `admit_anchored(root, baseline=..., attestation=..., trust=..., state_dir=...)` returns software PASS only after signature, regression, phase journal, anchor and SQLite commit. `recover(state_dir, permit=...)` is offline-only. No physical rail authorization.

## Phase model
IDLE -> PREPARED (SQLite durable commit) -> anchor replace + directory fsync -> IDLE (SQLite durable commit). SIGKILL before anchor publication can be resolved by discarding PREPARED; after anchor publication, the exact matching PREPARED can be completed. A mismatch blocks automatically.

## Safety and limitations
The anchor is a separate *file*, not an independently protected monotonic device: an attacker who can roll back both files defeats anti-rollback. SQLite, anchor and lock share an owner and filesystem. The permit is a caller-provided secret, not authenticated by a trusted authority, and its consumption is recorded in the same rollbackable SQLite file. No production IPC service is implemented; legacy library bypass remains. Filesystem races and privileged tampering are not comprehensively eliminated. Power-loss durability depends on filesystem and hardware guarantees. Do not treat local PASS as certification or operational GO.

## Verification
Unit tests cover private permissions, lock contention, anchor tampering, prepared recovery, ambiguous state, permit reuse, and symlink rejection. End-to-end train integration, cross-UID service operation, and authenticated permit issuance are not validated.
