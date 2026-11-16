# TrainOS Stage 87 — Verified backup and controlled restore

## Goal
Provide a fail-closed path for creating and restoring SQLite event-log backups against the separately stored integrity anchor.

## Implementation
- Added `EventLogBackupManager` with `create_backup`, `verify_backup`, and `restore_backup`.
- Uses SQLite's online backup API rather than copying a live database file, so committed state is captured consistently even when SQLite journaling modes differ.
- Builds backups/restores in temporary files, checks the resulting event log against the independent anchor, and only publishes a verified artifact.
- Rejects existing output destinations rather than silently overwriting them.
- Verification works against a temporary SQLite snapshot so schema migration during store initialization does not modify the supplied backup itself.
- Failed verification leaves no published backup or restored database.

## Validation
- Focused tests: `PYTHONPATH=. pytest -q tests/stage87 tests/stage86 tests/stage85` — 13 passed.
- Full suite: `PYTHONPATH=. pytest -q` — 640 passed.
- `python -m compileall -q kernel tests` — passed.
- AST parse of kernel Python files — recorded in the final stage report.
- Archive integrity checked with `unzip -t`.

## Limitations
- The anchor database remains separately trusted input and must be protected independently (ideally remote or WORM storage).
- SQLite backup and atomic rename do not by themselves provide cross-database atomicity or protect against a privileged attacker who can rewrite both event data and anchors.
- Destination paths must be new. This deliberately avoids replacing an active database or clobbering an existing file.
- This is application-level recovery tooling, not a safety-certified logging or train-control system.
