# Financial Ledger Contract v6 — Backup and Restore

## Scope

This additive stage implements consistent SQLite backup and guarded restore for the isolated ledger prototype. It does not connect the ledger to live payments or alter the legacy transaction API.

## API

- `FinancialLedger.backup_to(destination)` uses SQLite's online backup API to create a consistent snapshot, validates it, then publishes it with an atomic filesystem replace.
- `FinancialLedger.restore_from_backup(backup, destination, overwrite=False)` validates the source, restores to a staging file, validates the restored file, then publishes it atomically. Existing destinations are refused unless `overwrite=True` is explicit.
- File-backed databases only are supported for backup. Destination parent directories must already exist.

## Validation performed

- SQLite `integrity_check`.
- Foreign-key check.
- Required schema and `schema_version=1`.
- Every journal has postings and debit/credit totals balance by currency.
- Journal fingerprints are recomputed from canonical operation content.
- Restore is not published when validation fails.

## Limitations

- Fingerprints detect accidental or unsophisticated tampering, but they are not an authenticity mechanism: a party able to rewrite the database can also recompute hashes. Production audit integrity requires an external trust anchor or signed/externally anchored checkpoints.
- This is not an off-site backup scheduler, encryption/key management, retention policy, disaster-recovery runbook, or a guarantee against filesystem/hardware failure.
- Restore should be performed with application writers stopped. The caller owns access controls, destination permissions, retention and secure handling of backups.
- No real-money/payment integration is authorized by this stage.

## Acceptance status

Targeted unit tests cover backup/restore round-trip, balances and reconciliation after restore, refusal to overwrite by default, corrupt backup rejection, in-memory backup rejection and fingerprint mismatch detection. Full TrainOS suite is not claimed unless separately run.
