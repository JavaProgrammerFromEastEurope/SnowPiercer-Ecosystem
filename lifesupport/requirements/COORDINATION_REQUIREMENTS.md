# LIFE-CORE-006 requirements

All requirements below are software-prototype requirements, not physical safety acceptance criteria.

| ID | Requirement | Evidence |
|---|---|---|
| LIFE-COORD-001 | Grant a lease with nonzero epoch | test_initial_acquire |
| LIFE-COORD-002 | Reject competing owners while lease valid | test_exclusive_owner |
| LIFE-COORD-003 | Reject transitions without a valid token | test_no_token_rejected |
| LIFE-COORD-004 | Reject expired lease | test_expiry_rejects |
| LIFE-COORD-005 | Increment epoch on takeover | test_takeover_increments_epoch |
| LIFE-COORD-006 | Reject stale same-owner token | test_stale_same_owner |
| LIFE-COORD-007 | Support explicit release | test_release_allows_takeover |
| LIFE-COORD-008 | Invalidate old token on renewal | test_renew_updates_token |
| LIFE-COORD-009 | Reject invalid lease configuration | test_negative_ttl_rejected, test_empty_owner_rejected |
| LIFE-COORD-010 | Require fence for recovery | test_recover_requires_fence |
| LIFE-COORD-011 | Roll back rejected transitions | test_invalid_transition_rollback |
| LIFE-COORD-012 | Reject corrupt journal on opening/acquisition | test_corrupt_journal_blocks_acquire |
| LIFE-COORD-013 | Persist epoch across restarts | test_persists_epoch_across_restart |
| LIFE-COORD-014 | Reject changed registry fingerprint | test_registry_fingerprint_fenced |
| LIFE-COORD-015 | Allow sequential cooperating writers | test_two_writers_sequential |
| LIFE-COORD-016 | Document legacy bypass explicitly | test_legacy_is_not_fenced |
| LIFE-COORD-017 | Roll back if lease expires during operation | test_expiry_during_operation_rolls_back |
| LIFE-COORD-018 | Reject malformed token and duplicate release | test_invalid_token_type, test_double_release_rejected |
| LIFE-COORD-019 | Reject renewal after expiry | test_renew_expired_rejected |
