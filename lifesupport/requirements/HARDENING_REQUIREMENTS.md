# LIFE-CORE-008 Requirements

| ID | Requirement | Verification |
|---|---|---|
| LIFE-HARD-001 | Preserve unprotected journal compatibility | test_unprotected_compatible |
| LIFE-HARD-002 | Support explicit v1 to v2 migration | test_migrate_v1 |
| LIFE-HARD-003 | Make migration idempotent | test_harden_idempotent |
| LIFE-HARD-004 | Require valid fence token | test_harden_requires_fence |
| LIFE-HARD-005 | Require prior protection | test_harden_requires_protection |
| LIFE-HARD-006 | Detect missing insert guard | test_insert_guard_removed |
| LIFE-HARD-007 | Detect modified update guard | test_update_guard_changed |
| LIFE-HARD-008 | Detect missing delete guard | test_delete_guard_removed |
| LIFE-HARD-009 | Detect modified seal | test_seal_changed |
| LIFE-HARD-010 | Detect missing seal table | test_seal_missing |
| LIFE-HARD-011 | Fail closed on hardened open | test_open_detects_tamper |
| LIFE-HARD-012 | Permit valid fenced writes | test_valid_write |
| LIFE-HARD-013 | Reject unauthorized legacy writes | test_legacy_rejected |
| LIFE-HARD-014 | Roll back failed migration | test_rollback_bad_migration |
| LIFE-HARD-015 | Keep stable digest format | test_digest_stable |
| LIFE-HARD-016 | Preserve seal across restart | test_reopen_clean |
