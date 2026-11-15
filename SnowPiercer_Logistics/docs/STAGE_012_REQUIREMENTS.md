# LOG-CORE-012 requirements
R12-01: preserve public library APIs and all earlier tests.
R12-02: reject duplicate or unsafe deployment UIDs, roots and socket placement.
R12-03: privileged installer must use descriptor-based no-follow operations and never recursively chown data.
R12-04: production entrypoint must remain fail-closed without independent OS attestation.
R12-05: run three full strict warning regressions and retain results.
R12-06 (OPEN): deploy real distinct UIDs, demonstrate legacy OS fencing and end-to-end recovery.
R12-07 (OPEN): exhaustive SIGKILL matrix, rollback to genesis, file/socket tampering and independent witness evidence.
