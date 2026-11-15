# LIFE-CORE-010 Requirements

| ID | Requirement | Verification |
|---|---|---|
| LIFE-ROT-001 | Require a distinct new key of >=32 bytes | test_short_key, test_same_key |
| LIFE-ROT-002 | Authenticate pending intent with both keys | test_tamper_pending |
| LIFE-ROT-003 | Refuse duplicate preparation | test_double_prepare |
| LIFE-ROT-004 | Require valid fencing token for preparation | test_invalid_token |
| LIFE-ROT-005 | Block writes through rotation API while pending | test_pending_blocks_write |
| LIFE-ROT-006 | Reject incorrect new key | test_wrong_new_key |
| LIFE-ROT-007 | Make new anchor verifiable with new key | test_new_key_reopens |
| LIFE-ROT-008 | Reject old key after finalization | test_old_key_rejected |
| LIFE-ROT-009 | Classify interruption without mutation | test_prepare |
| LIFE-ROT-010 | Reject tampered anchor during reconciliation | test_tamper_anchor |
| LIFE-ROT-011 | Refuse normal rotation-aware opening while pending | test_pending_blocks_reopen |
| LIFE-ROT-012 | Refuse missing intent during reconciliation | test_missing_pending |
| LIFE-ROT-013 | Retain previous Stage tests | full regression |
| LIFE-ROT-014 | Close SQLite connections in test helpers | ResourceWarning strict regression |
