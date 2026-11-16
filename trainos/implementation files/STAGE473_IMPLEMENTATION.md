# Stage 473 — Missing Destination Parent Is Handled Without Leaked Temp Files

## Goal

missing destination parent is handled without leaked temp files.

## Implementation

This stage extends the financial-ledger backup validation and recovery contract. The validator operates read-only and reports findings instead of repairing a backup during acceptance.

## Verification

Run the stage-specific test with `python -m pytest tests/stage473 -q`.
