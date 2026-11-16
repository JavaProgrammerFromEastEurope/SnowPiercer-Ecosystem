# Stage 471 — Audit Table Primary Key Requirement Is Enforced

## Goal

audit table primary key requirement is enforced.

## Implementation

This stage extends the financial-ledger backup validation and recovery contract. The validator operates read-only and reports findings instead of repairing a backup during acceptance.

## Verification

Run the stage-specific test with `python -m pytest tests/stage471 -q`.
