# LOG-CORE-020 requirements and acceptance

R-020-01 preserve all previous public library interfaces (tested with cumulative suite).
R-020-02 reject colliding, root or mismatched service/witness/authority/client UIDs (implemented).
R-020-03 reject non-socket, symlink, wrong-owner or world-writable IPC endpoint (implemented; parent TOCTOU remains).
R-020-04 fail closed before production socket publication (implemented: unconditional NO-GO).
R-020-05 integrated four-UID ledger/witness/permit/recovery E2E (NOT IMPLEMENTED).
R-020-06 OS-enforced legacy fencing across production entrypoints (NOT PROVEN).
R-020-07 exhaustive SIGKILL and tamper matrix (NOT IMPLEMENTED).
R-020-08 three strict cumulative regressions (verified).
