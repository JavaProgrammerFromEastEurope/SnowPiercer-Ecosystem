# Stage 506 — Test Stage506 Unknown Multi Generation

## Goal
Strengthen read-only backup acceptance for reconciliation audit history.

## Implementation
Extended the audit validation contract and added a focused regression test for this invariant. Validation must reject inconsistent audit evidence without mutating source data.

## Verification
Run `python -m pytest tests/stage506`. Release-wide regression results are recorded in the v59 manifest after execution.
