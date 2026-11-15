# LIFE-CORE-011 requirements and traceability

| ID | Requirement | Verification |
|---|---|---|
| LIFE-CORE-011-REQ-001 | Persist rotation fence before publishing prepared intent | Source review and `test_pending_marker_survives_close_and_reopen` |
| LIFE-CORE-011-REQ-002 | Reject legacy admitted INSERT while rotation pending | `test_existing_legacy_writer_blocked_during_rotation` |
| LIFE-CORE-011-REQ-003 | Keep rejection after process SIGKILL | `test_subprocess_sigkill_after_prepare` |
| LIFE-CORE-011-REQ-004 | Fail closed for orphan fence | `test_marker_without_intent_fails_closed` |
| LIFE-CORE-011-REQ-005 | Preserve fence on invalid new key | `test_invalid_new_key_keeps_fence` |
| LIFE-CORE-011-REQ-006 | Remove fence after successful finalization | `test_legacy_writer_resumes_after_finalize` |
| LIFE-CORE-011-REQ-007 | Do not affect separate database | `test_unprotected_database_not_affected_by_other_marker` |
| LIFE-CORE-011-REQ-008 | Preserve existing regression and resource hygiene | full `unittest -W error::ResourceWarning` |

These are software requirements; not certified safety requirements.
