# LIFE-CORE-019 requirements

| ID | Requirement | Verification |
|---|---|---|
| LIFE-019-01 | Fail closed if protected v2 schema is absent | startup preflight |
| LIFE-019-02 | Authenticate anchor with independently provisioned HMAC key | wrong-key test |
| LIFE-019-03 | Persist intent before SQLite transaction | after-intent fault |
| LIFE-019-04 | Commit event and receipt in one SQLite transaction | inherited LIFE-017 tests |
| LIFE-019-05 | Reconcile only one exactly matching appended receipt | after-COMMIT recovery |
| LIFE-019-06 | Reject unexpected receipt changes or deletion | tamper tests |
| LIFE-019-07 | Reject malformed/tampered pending intent | tamper test |
| LIFE-019-08 | Gate IPC read/write and startup on recovery admission | code inspection and tests |
| LIFE-019-09 | Preserve legacy API compatibility | regression suite |
| LIFE-019-10 | Preserve authorization by kernel peer UID | inherited cross-UID tests |
| LIFE-019-11 | Do not expose key through IPC | code inspection |
| LIFE-019-12 | Reject concurrent intent acquisition | intent existence check; no multi-process lock proof |
| LIFE-019-13 | Document power-loss and rollback limitations | safety review |
