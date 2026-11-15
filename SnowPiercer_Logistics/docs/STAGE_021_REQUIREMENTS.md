# LOG-CORE-021 — timed TrainOS command integration

Version: 0.21.0. Scope: an opt-in local ledger adapter; operational admission is
still BLOCKED / NO-GO.

| ID | Criterion | Evidence |
| --- | --- | --- |
| R-021-01 | Admit only the closed schema version 1 and the seven existing typed ledger actions; reject client identity fields and unsupported/recovery actions. | `test_malformed_or_unsupported_envelope_rejected_without_effect`, `test_client_identity_field_rejected` |
| R-021-02 | Reject future or expired commands, including expiry while acquiring the SQLite lock. Deadline equality is expired. | `test_expired_or_future_envelopes_rejected`, `test_expiry_rechecked_after_transaction_lock_acquisition`, `test_expired_replay_is_not_admitted` |
| R-021-03 | Compare expected event count and record receipt in the same `BEGIN IMMEDIATE` transaction as the cargo effect. Two connections racing from the same revision admit at most one distinct command. | `test_independent_connections_compare_revision_atomically` |
| R-021-04 | Return a cached result only for the same principal and byte-equivalent canonical envelope. Persist the binding across reopen and concurrent duplicates. | replay, changed-envelope, different-principal, reopen and concurrent-duplicate tests |
| R-021-05 | Recheck current host-supplied permissions before replay and reject writes outside the envelope API on the opt-in ledger. | `test_revoked_role_cannot_replay_committed_result`, `test_direct_write_cannot_bypass_opt_in_envelope_policy` |
| R-021-06 | Roll back the integration receipt when the cargo operation fails, and reject collisions with legacy keys. | `test_failed_mutation_rolls_back_receipt_and_allows_valid_retry`, `test_legacy_command_key_is_not_silently_imported` |
| R-021-07 | Preserve prior ledger/service APIs and keep production admission closed. | cumulative strict pytest regression; `test_production_admission_remains_closed` |

33 new tests cover these criteria. Earlier privileged scenarios may remain
skipped by their existing platform/UID conditions and are recorded separately
from passing tests. The next stage does not retroactively prove those scenarios.
