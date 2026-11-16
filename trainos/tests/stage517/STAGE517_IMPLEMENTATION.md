# Stage 517 — Audit Generation Integrity

## Goal
Strengthen the financial-ledger backup acceptance contract with a focused regression test for audit sequence integrity, current dispatch generation coverage, read-only validation, or stable copy/reopen behavior.

## Implementation
The implementation lives in `kernel/command/execution/command_idempotency_store.py`. Backup validation remains read-only and reports integrity findings instead of silently repairing history.

## Verification
Run `python -m pytest tests/stage517` from the repository root.
