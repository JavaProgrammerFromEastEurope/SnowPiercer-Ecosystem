# LOG-CORE-016 requirements and verification

Target: integrated ledger, independent witness CAS, direct-client attested permits, four independent UIDs, OS-enforced legacy fencing and exhaustive SIGKILL coverage.

Implemented scope: opt-in consistency gate for read/recover IPC; explicit rejection of legacy permit issuance; disposable SIGKILL probe; fail-closed production admission. Existing APIs preserved.

Unmet requirements: integrated four-UID transaction, OS-enforced legacy fencing for all entry points, rollback resistance to genesis, atomic distributed recovery, exhaustive fault injection and tamper matrix. Production BLOCKED/NO-GO.
