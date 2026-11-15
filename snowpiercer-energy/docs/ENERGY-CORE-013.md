# ENERGY-CORE-013 — Independent Recovery Authorization Anchoring & Production Bypass Closure

Status: PARTIAL / BLOCKED; physical operation NO-GO.

## Requirements and evidence
- R013-01: Detect permit DB rollback against a separate checkpoint: implemented for cooperative single-directory trust, tests `test_db_rollback_detected`.
- R013-02: Detect missing and substituted checkpoint: implemented, tests `test_checkpoint_missing_detected`, `test_checkpoint_symlink_detected`.
- R013-03: UID-bound single-use permits: inherited from CORE-011/012; tested in stage 013.
- R013-04: Three full strict regressions: evidence logs included.
- R013-05: Independent trust boundary: BLOCKED. The checkpoint and permit DB are both writable by the same OS principal; coordinated rollback is not detectable.
- R013-06: Mandatory production fencing of all legacy paths: BLOCKED. Existing public `PersistentEnergyLedger.apply()` remains accessible. No verified OS-level isolation.
- R013-07: Real different-UID end-to-end verification: NOT EXECUTED.
- R013-08: Exhaustive SIGKILL at SQLite, phase journal, anchor, IPC: NOT EXECUTED. CORE-012 selected os._exit points are not exhaustive.
- R013-09: Full ledger rollback-to-genesis and file/socket/lock substitution matrix: NOT EXECUTED in this stage.

## Architecture and contracts
`AnchoredDurableEnergyService(DurableEnergyService)` is an opt-in, simulation-only API. It requires a private checkpoint directory owned by the effective UID. The checkpoint contains SHA-256 over a canonical, sorted snapshot of permit records. The `permits.guard` advisory flock serializes cooperating service instances; the existing admission lock protects the underlying ledger operations. Issuance and consumption update the checkpoint after the permit database commit. A crash in this window creates a mismatch and prevents subsequent operations (fail closed); there is no automatic repair. Checkpoint replacement uses fsync on file and directory. UID checks remain those of the inherited service.

## Safety analysis
- S013-01: Coordinated replacement of permit DB and checkpoint: undetected; independent WORM/HSM/remote attestation required.
- S013-02: Crash after permit commit before checkpoint update: denial of service requiring independently authorized reconciliation; no silent rollback.
- S013-03: Legacy direct ledger API: bypasses new checkpoint; production NO-GO.
- S013-04: Same-UID malicious process can manipulate both files and lock paths; filesystem ownership alone is not a trust root.
- S013-05: IPC UID auth cannot replace capability isolation or separate service identities.
- S013-06: Neither actual power hardware nor physical interlocks are modeled or tested.

## Acceptance
Programmatic regression: PASS in recorded environment. Mandatory production admission, independent authorization anchoring, cross-UID verification and physical readiness: BLOCKED / NO-GO.
