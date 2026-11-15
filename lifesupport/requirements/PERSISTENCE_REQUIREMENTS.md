# LIFE-CORE-004 requirements and traceability

| ID | Requirement | Verification |
|---|---|---|
| LIFE-PERSIST-001 | Restore state from committed journal on restart | test_restart_replay |
| LIFE-PERSIST-002 | Reject replayed event IDs after restart | test_duplicate_after_restart |
| LIFE-PERSIST-003 | Reject invalid transition without persistence | test_invalid_transition_atomic |
| LIFE-PERSIST-004 | Reject modified event payloads | test_tamper_payload_detected |
| LIFE-PERSIST-005 | Reject missing internal journal events | test_missing_middle_detected |
| LIFE-PERSIST-006 | Bind journal to registry fingerprint | test_fingerprint_mismatch |
| LIFE-PERSIST-007 | Serialize and refresh stale writers | test_stale_writer_replays |
| LIFE-PERSIST-008 | Reject replay across concurrent instances | test_stale_duplicate_rejected |
| LIFE-PERSIST-009 | Preserve committed state after rejected transition | test_failed_insert_rollback |
| LIFE-PERSIST-010 | Explicitly refresh in-memory state | test_recover_after_external_event |
| LIFE-PERSIST-011 | Reject malformed stored JSON | test_truncated_json_detected |
| LIFE-PERSIST-012 | Preserve sequence numbers after restart | test_event_sequence_persisted |
| LIFE-PERSIST-013 | Reject index/payload identity mismatch | test_event_index_tamper_detected |
| LIFE-PERSIST-014 | Provide no hardware control interface | test_no_hardware_interface |
| LIFE-PERSIST-015 | Empty database starts in REGISTERED | test_initial_empty |

Verification applies only to software unit tests, not to deployment or physical safety.
