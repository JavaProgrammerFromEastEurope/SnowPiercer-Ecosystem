# Stage 470 — Duplicate Reconciliation Events Are Rejected

## Goal

duplicate reconciliation events are rejected.

## Implementation

This stage extends the financial-ledger backup validation and recovery contract. The validator operates read-only and reports findings instead of repairing a backup during acceptance.

## Verification

Run the stage-specific test with `python -m pytest tests/stage470 -q`.
