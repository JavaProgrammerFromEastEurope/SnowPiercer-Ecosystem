# LOG-CORE-017 requirements and disposition
- R17-01 Preserve prior public Python interfaces: local regression PASS.
- R17-02 Classify ledger/local checkpoint/independent witness divergence: implemented opt-in, unit tested.
- R17-03 Reject pending phase journal before startup and before operations: implemented opt-in.
- R17-04 Read phase journal without following symlinks: descriptor-based Linux/POSIX O_NOFOLLOW; unit tested.
- R17-05 Integrated four-UID ledger/witness/attestation/recovery E2E: NOT MET.
- R17-06 Mandatory production IPC and OS-enforced legacy fencing: NOT MET.
- R17-07 Exhaustive SIGKILL, replay, rollback, concurrent processes, tampering matrix: NOT MET.
- R17-08 Independent evidence and production release: NOT MET; BLOCKED/NO-GO.
