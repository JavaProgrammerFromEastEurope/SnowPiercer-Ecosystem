# LOG-CORE-019 Requirements and acceptance

R-019-01: retain Stage 001-018 APIs and tests. VERIFIED by three strict full pytest regressions.
R-019-02: reject legacy permit issuance on opt-in transaction endpoint. VERIFIED locally.
R-019-03: reject symlink, non-socket and world-writable authority endpoints. VERIFIED locally.
R-019-04: verify ledger/checkpoint/witness/phase before dispatch. VERIFIED by inherited consistency tests and unit checks; no atomicity claim.
R-019-05: actual four-UID ledger -> witness CAS -> attestation -> recover E2E. NOT MET.
R-019-06: mandatory production entrypoint and OS-enforced legacy fencing. NOT MET.
R-019-07: exhaustive SIGKILL / rollback / tamper matrix. NOT MET.
Acceptance: BLOCKED / NO-GO.
