# LIFE-CORE-021 acceptance requirements

| ID | Criterion | Evidence |
| --- | --- | --- |
| LIFE-021-R01 | Admit only registered metrics, units and allowed component identities using trusted local policy. | `test_unknown_metric_and_unexpected_payload_fields_are_rejected`, `test_unknown_and_unauthorized_sources_are_rejected`, `test_wrong_unit_rejected_instead_of_implicit_conversion` |
| LIFE-021-R02 | Reject stale/future observations and invalid UTC timestamps; sender cannot widen age policy. | Boundary, stale, future, UTC and sender override tests in `test_telemetry.py` |
| LIFE-021-R03 | Reject non-finite values, boolean values/sequences and non-GOOD quality before state mutation. | `test_nonfinite_and_boolean_values_are_rejected`, `test_invalid_sequences_are_rejected`, `test_invalid_or_suspect_quality_is_not_a_current_good_value` |
| LIFE-021-R04 | Reject replay IDs, decreasing sequences, decreasing observation time and clock rollback. | Replay, sequence and clock tests in `test_telemetry.py` |
| LIFE-021-R05 | Capacity exhaustion must fail closed without forgetting admitted identities. | `test_capacity_fails_closed_without_forgetting_replay_ids` |
| LIFE-021-R06 | Invalid input cannot poison clock/replay state; output and policy snapshots are detached from mutable input. | Rejected-state, immutability and policy snapshot tests |
| LIFE-021-R07 | Commands remain disabled and no actuator authority is exported. | `test_commands_and_other_message_kinds_remain_disabled` and legacy command tests |
| LIFE-021-R08 | Full cumulative regression and correlated read-only probe produce separately retained evidence. | `evidence/LIFE-CORE-021_TEST_RESULTS.txt`, `integration_probe.py` |
