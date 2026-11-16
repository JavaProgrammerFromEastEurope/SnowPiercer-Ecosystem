# Stage 503 — Test Stage503 Reopen Preserves Decisions

## Goal
Strengthen read-only backup acceptance for reconciliation audit history.

## Implementation
Extended the audit validation contract and added a focused regression test for this invariant. Validation must reject inconsistent audit evidence without mutating source data.

## Verification
Run `python -m pytest tests/stage503`. Release-wide regression results are recorded in the v59 manifest after execution.
