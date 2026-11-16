# Stage 507 — Test Stage507 End To End Audit Recovery

## Goal
Strengthen read-only backup acceptance for reconciliation audit history.

## Implementation
Extended the audit validation contract and added a focused regression test for this invariant. Validation must reject inconsistent audit evidence without mutating source data.

## Verification
Run `python -m pytest tests/stage507`. Release-wide regression results are recorded in the v59 manifest after execution.
