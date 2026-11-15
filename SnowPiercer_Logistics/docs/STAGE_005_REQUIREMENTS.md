# LOG-CORE-005 requirements and disposition

- R005-01 Witness monotonic compare-and-swap: IMPLEMENTED, local tests.
- R005-02 Kernel-derived UID authentication at witness socket: IMPLEMENTED, simulated UID denial tested; distinct OS accounts NOT TESTED.
- R005-03 Witness-backed fail-closed startup: IMPLEMENTED, local tests.
- R005-04 Separate witness process and UID: PROCESS CAPABLE, deployment NOT VERIFIED.
- R005-05 OS-enforced legacy production fencing: NOT IMPLEMENTED.
- R005-06 Crash-point exhaustive SIGKILL matrix: NOT COMPLETED.
- R005-07 Real cross-UID end-to-end: NOT COMPLETED.
- R005-08 Rollback-to-genesis under attacker-controlled files: PARTIAL.
- R005-09 Preserve prior API: EXISTING 28 TESTS PASS.
- R005-10 Three strict regressions: see evidence logs.

Release decision: BLOCKED / NO-GO.
