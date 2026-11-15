# Preliminary hazard analysis — LIFE-CORE-009

| Hazard | Cause | Mitigation | Residual risk |
|---|---|---|---|
| TA-H01 | Anchor and key compromised | Separate provisioning, HMAC | High without HSM |
| TA-H02 | Anchor missing or corrupted | Fail closed in TrustedLifecycle | Availability loss |
| TA-H03 | DB rollback | External epoch floor | Only detects rollback below published floor |
| TA-H04 | Bypass via legacy API | Document and restrict deployment access | High until enforcement at storage boundary |
| TA-H05 | Crash between DB and anchor update | Explicit operator reconciliation | Inconsistent trust state |
| TA-H06 | Stolen signing key | Key rotation procedure required | Not implemented |
| TA-H07 | Tampered SQLite schema | Guard verification | Privileged bypass remains |

Operational readiness: NO-GO. Independent security review and failure-injection testing required.
