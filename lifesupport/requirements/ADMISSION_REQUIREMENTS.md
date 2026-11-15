# LIFE-CORE-007 requirements

| ID | Requirement | Verification |
|---|---|---|
| LIFE-ADM-001 | Protected journals reject legacy event append | test_protection_blocks_legacy |
| LIFE-ADM-002 | Admitted fenced writer can append | test_admitted_append |
| LIFE-ADM-003 | Revoked token cannot append | test_stale_token_rejected |
| LIFE-ADM-004 | Migration requires valid token | test_protect_requires_token |
| LIFE-ADM-005 | Migration is idempotent | test_migration_idempotent |
| LIFE-ADM-006 | Existing history survives migration | test_migration_legacy_events |
| LIFE-ADM-007 | Unregistered raw SQLite connection cannot append | test_raw_sql_rejected |
| LIFE-ADM-008 | Protected event updates and deletes are denied | test_delete_and_update_rejected |
| LIFE-ADM-009 | Admission survives process restart | test_restart_protection_persists |
| LIFE-ADM-010 | Legacy unprotected DB stays writable | test_unprotected_legacy_unchanged |
| LIFE-ADM-011 | Admission flag resets on error | test_failed_transition_flag_reset |
| LIFE-ADM-012 | Failed migration rolls back | test_failed_protect_rolls_back |
