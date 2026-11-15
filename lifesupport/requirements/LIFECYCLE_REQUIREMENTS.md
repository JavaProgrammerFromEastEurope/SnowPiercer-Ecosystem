# LIFE-CORE-003 Requirements

| ID | Requirement | Verification |
|---|---|---|
| LREQ-LC-001 | Initialize every registry component as REGISTERED | test_initial_state_all |
| LREQ-LC-002 | Permit only enumerated state transitions | test_no_jump, test_same_state, test_transition_table_complete |
| LREQ-LC-003 | Reject ACTIVE entry if direct dependencies are not ACTIVE | test_dependency_guard |
| LREQ-LC-004 | Prevent normal ACTIVE exit with active direct dependents | test_reverse_dependency_guard |
| LREQ-LC-005 | Reject duplicate event IDs | test_duplicate_event_rejected |
| LREQ-LC-006 | Validate event metadata and UTC timestamps | test_invalid_metadata_atomic, test_utc_required |
| LREQ-LC-007 | Reject nonmonotonic event timestamps | test_monotonic_time |
| LREQ-LC-008 | Provide a sequential, verifiable hash-linked event log | test_hash_chain, test_tamper_detected |
| LREQ-LC-009 | Failed transitions must not mutate state | test_failed_transition_no_event |
| LREQ-LC-010 | Expose immutable event objects and detached snapshots | test_events_immutable, test_snapshot_copy |
| LREQ-LC-011 | Preserve LIFE-CORE-002 APIs and tests | test_registry.py regression suite |
| LREQ-LC-012 | Do not expose actuation APIs | test_no_actuation_interface |

These are software model requirements, not validated environmental or human safety requirements. Status: local test evidence only.
