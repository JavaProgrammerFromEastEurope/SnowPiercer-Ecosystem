# Stage 469 — Utc Ordering Compares Instants Rather Than Timestamp Strings

## Goal

UTC ordering compares instants rather than timestamp strings.

## Implementation

This stage extends the financial-ledger backup validation and recovery contract. The validator operates read-only and reports findings instead of repairing a backup during acceptance.

## Verification

Run the stage-specific test with `python -m pytest tests/stage469 -q`.
