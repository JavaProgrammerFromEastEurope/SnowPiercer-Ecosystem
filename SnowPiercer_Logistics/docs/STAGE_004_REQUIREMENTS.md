# LOG-CORE-004 Requirements and acceptance
R004-01: Maintain compatibility with LOG-CORE-001..003 public library API. VERIFIED by regression.
R004-02: Hold single-writer process lock for full service lifetime. VERIFIED locally.
R004-03: Fail closed on symlink and ownership violations at IPC dispatch. PARTIALLY VERIFIED.
R004-04: Bind recovery permits to kernel-derived UID, single use. INHERITED, locally tested; multi-UID E2E NOT VERIFIED.
R004-05: Independent external trust anchor. NOT IMPLEMENTED.
R004-06: OS-enforced denial of direct legacy database writes. NOT IMPLEMENTED.
R004-07: Exhaustive SIGKILL boundary verification. NOT COMPLETED.
R004-08: Three strict full regressions, preserving failures. Test runs documented in evidence.
Production acceptance: BLOCKED / NO-GO.
