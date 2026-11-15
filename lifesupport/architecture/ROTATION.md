# LIFE-CORE-010 — Key Rotation and Recovery Reconciliation

- Scope: offline logical state journal; not safety-certified and not physical control.
- Rotation is opt-in through `RotatingLifecycle`. Previous `TrustedLifecycle` remains unchanged.
- `prepare_rotation(token, new_key)` creates an exclusive pending file, HMAC-authenticated with both keys. The old anchor remains valid.
- `finalize_rotation(token, new_key)` authenticates the pending record, checks fencing and journal replay, writes the new anchor, then removes the pending record.
- `inspect_interrupted_rotation(anchor_path, old_key, new_key)` performs read-only classification: `OLD_ANCHOR` or `NEW_ANCHOR`; mismatches fail closed.
- The pending file blocks writes through `RotatingLifecycle`; no automatic cleanup occurs. A failed finalization can leave the new anchor and pending file. Operators must independently validate state and keys before manual reconciliation.
- Trust assumptions: anchor, pending file, and both keys have appropriate access control. No HSM, external monotonic clock, distributed consensus, atomic cross-file transaction, or adversarial privileged-writer resistance.
- Durability limitation: the pending file is fsynced, but its parent directory is not; cross-file crash consistency is not guaranteed. This is not a production recovery protocol.
- `TrustedLifecycle` and older APIs do not automatically honor rotation pending files: mandatory cross-API enforcement remains an open risk.
