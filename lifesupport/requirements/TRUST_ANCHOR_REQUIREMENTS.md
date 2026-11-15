# LIFE-CORE-009 requirements

| ID | Requirement | Verification |
|---|---|---|
| LIFE-TA-001 | Store configuration anchor outside SQLite | test_enrollment |
| LIFE-TA-002 | Authenticate anchor with HMAC-SHA256 | test_modified_mac |
| LIFE-TA-003 | Reject wrong secret | test_wrong_key |
| LIFE-TA-004 | Reject malformed anchor | test_truncated_file |
| LIFE-TA-005 | Reject missing enrolled anchor | test_missing_anchor |
| LIFE-TA-006 | Reject modified payload | test_modified_payload |
| LIFE-TA-007 | Reject rollback below anchored epoch floor | test_rollback_epoch |
| LIFE-TA-008 | Require protected v2 journal for enrollment | test_enroll_requires_v2 |
| LIFE-TA-009 | Require fencing for enrollment | test_enroll_requires_fence |
| LIFE-TA-010 | Reject repeated enrollment | test_double_enrollment |
| LIFE-TA-011 | Validate anchor before lifecycle write | test_valid_write |
| LIFE-TA-012 | Reject modified guard | test_tamper_guard |
| LIFE-TA-013 | Support reopen with valid anchor | test_reopen |
| LIFE-TA-014 | Advance external epoch floor explicitly | test_advance_anchor |
| LIFE-TA-015 | Require fencing for floor advancement | test_advance_requires_fence |
| LIFE-TA-016 | Reject unanchored acquisition after enrollment | test_no_anchor_blocks_acquire |
| LIFE-TA-017 | Preserve prior unprotected compatibility | test_legacy_unprotected |
| LIFE-TA-018 | Require 256-bit minimum HMAC key | test_short_secret |
