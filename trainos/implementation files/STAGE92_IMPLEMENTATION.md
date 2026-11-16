# TrainOS Stage 92 — Atomic no-clobber publication

## Scope

Closed the time-of-check/time-of-use race in verified SQLite backup and restore publication. Previously, checking that a destination did not exist and then calling `os.replace` could overwrite a file created by another process between those operations.

## Implementation

- Added `EventLogBackupManager._publish_no_clobber()`.
- Publishes a fully closed and verified temporary file through same-filesystem `os.link`, whose target creation fails atomically if the destination already exists.
- Removes the temporary name only after successful publication.
- Does not fall back to `os.replace`; filesystems that do not support hard links fail closed rather than risk clobbering another file.
- Both backup creation and recovery-candidate restoration use the shared publication helper.

## Verification

- Tests simulate a competing writer creating the destination precisely at publication time for both backup creation and restore.
- Tests assert that the competitor's bytes survive unchanged and the operation reports `FileExistsError`.
- Direct helper test confirms an existing target and unpublished temporary file are both preserved on collision.

## Limits

This is an application-level atomic no-clobber safeguard, not protection against privileged or malicious filesystem actors. It assumes temporary and destination paths are on the same filesystem (the implementation places the temporary file in the destination directory). It does not promote a recovery candidate to the active database and does not establish safety certification for physical train control.
