# TrainOS Stage 75 — Registry-backed evidence validation

## Change
- Added `EventRegistry.all_events()` to expose a deterministic snapshot of events still retained in the existing in-memory registry.
- Added `DiagnosticEvidenceValidator.validate_from_registry()` to connect the existing event registry to evidence-reference validation.
- The adapter always marks history as incomplete because `EventRegistry` is bounded per command and in-memory. Missing event references therefore remain warnings; this API never claims that the event never existed.
- Existing validation remains the single source of validation rules; no duplicate validator or durable-event-store claim was introduced.

## Verification
- Stage 75 + Stage 74 + Stage 56 focused tests: 13 passed.
- Full suite: **579 passed in 3.05s**, pytest exit code 0.
- `python3 -m compileall -q kernel tests`: passed.
- AST parse of all **2,127** `kernel/**/*.py` files: **0 errors**.

## Limits
`EventRegistry` is not an authoritative durable event log. A complete-history result must only be requested by callers that independently establish completeness from an authoritative source. This stage does not change persistence, retention, or event sourcing guarantees.
