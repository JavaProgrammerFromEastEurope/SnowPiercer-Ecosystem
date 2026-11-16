# Stage 449: Backup Validation Checks Sequence Primary Key

## Contract

This stage adds a focused regression contract for backup validation checks sequence primary key. The test uses a temporary SQLite database and checks safe failure or preservation behavior without contacting an external provider.

## Verification

Run: `python -m pytest tests/stage449 -q`

## Boundary

This is a local SQLite behavior check, not a distributed-storage guarantee or payment-provider certification.
