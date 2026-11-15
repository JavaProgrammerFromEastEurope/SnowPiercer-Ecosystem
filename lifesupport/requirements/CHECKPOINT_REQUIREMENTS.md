# LIFE-CORE-005 Requirements

| ID | Requirement | Verification |
|---|---|---|
| LIFE-CORE-005-REQ-001 | Persist authenticated journal head with sequence and event digest | test_anchor_roundtrip |
| LIFE-CORE-005-REQ-002 | Bind checkpoint to registry fingerprint | test_anchor_roundtrip |
| LIFE-CORE-005-REQ-003 | Reject incorrect HMAC key | test_bad_key |
| LIFE-CORE-005-REQ-004 | Reject edited checkpoint | test_tampered_anchor |
| LIFE-CORE-005-REQ-005 | Detect journal truncated below anchor | test_detect_truncated_tail |
| LIFE-CORE-005-REQ-006 | Detect divergent history at anchored sequence | test_detect_rewritten_history |
| LIFE-CORE-005-REQ-007 | Reject locally detectable anchor rollback | test_anchor_no_rollback |
| LIFE-CORE-005-REQ-008 | Allow valid unanchored tail by policy | test_anchor_allows_new_events |
| LIFE-CORE-005-REQ-009 | Produce replay-verified SQLite backup | test_backup_roundtrip |
| LIFE-CORE-005-REQ-010 | Authenticate backup digest and head | test_manifest_tamper |
| LIFE-CORE-005-REQ-011 | Reject modified backup bytes | test_backup_tamper |
| LIFE-CORE-005-REQ-012 | Reject incorrect backup authentication key | test_wrong_backup_key |
| LIFE-CORE-005-REQ-013 | Restore to new destination only | test_no_overwrite_restore |
| LIFE-CORE-005-REQ-014 | Reject invalid backup against anchored history | test_backup_rejects_old_anchor |
| LIFE-CORE-005-REQ-015 | Require a minimum secret length | test_short_key |
| LIFE-CORE-005-REQ-016 | Reject backup path aliasing | test_distinct_paths |

Verification is unit-level only, not independent safety certification.
