# Stage 472 — Corrupt Backup Reads Fail Closed

## Goal

corrupt backup reads fail closed.

## Implementation

This stage extends the financial-ledger backup validation and recovery contract. The validator operates read-only and reports findings instead of repairing a backup during acceptance.

## Verification

Run the stage-specific test with `python -m pytest tests/stage472 -q`.
