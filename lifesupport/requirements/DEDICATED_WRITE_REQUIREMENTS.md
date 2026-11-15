# LIFE-CORE-016 Requirements

| ID | Requirement | Verification |
|---|---|---|
| LIFE-016-REQ-01 | Service must reject root and same-UID client configurations | unit test |
| LIFE-016-REQ-02 | Peer UID must be verified by Linux kernel credentials | unit/integration |
| LIFE-016-REQ-03 | DB directory must be service-owned 0700 and DB files 0600 | integration |
| LIFE-016-REQ-04 | Write API must accept only exact transition fields | unit |
| LIFE-016-REQ-05 | Audit actor must derive from verified UID | code review/integration |
| LIFE-016-REQ-06 | Write must use server-issued fenced transaction | code review/integration |
| LIFE-016-REQ-07 | Service must refuse unprotected database | integration |
| LIFE-016-REQ-08 | Different unprivileged UID must not open SQLite directly | integration |
| LIFE-016-REQ-09 | Restart after SIGKILL must replay committed journal | integration |
| LIFE-016-REQ-10 | Concurrent invalid transitions must not corrupt journal | integration |
| LIFE-016-REQ-11 | Old APIs must remain import-compatible | full regression |
| LIFE-016-REQ-12 | ResourceWarning must be treated as test failure | full regression |
