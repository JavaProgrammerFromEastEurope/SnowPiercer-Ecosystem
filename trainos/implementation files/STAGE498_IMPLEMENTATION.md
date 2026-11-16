# Stage 498 — Test Stage498 Conflicting Decisions

## Goal
Strengthen read-only backup acceptance for reconciliation audit history.

## Implementation
Extended the audit validation contract and added a focused regression test for this invariant. Validation must reject inconsistent audit evidence without mutating source data.

## Verification
Run `python -m pytest tests/stage498`. Release-wide regression results are recorded in the v59 manifest after execution.
