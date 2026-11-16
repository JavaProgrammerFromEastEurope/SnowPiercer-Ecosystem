# TrainOS Stage 56 — Diagnostic evidence quality validation

## Implemented

- Added `DiagnosticEvidenceValidator`, a read-only validator over `HypothesisRegistrySnapshot` and a caller-supplied inventory of `CommandEvent` objects.
- Verifies that the originating diagnostic event exists, has the expected integrity-diagnostic type, carries the same diagnostic code, and belongs to the command recorded in the hypothesis.
- Checks assessment references for missing evidence, ambiguous duplicate event IDs, orphan assessments, duplicate evidence references, invalid assessment timestamps, evidence recorded after assessment, and cross-command evidence.
- Distinguishes missing references in a possibly bounded history (warning) from missing references in a caller-declared complete inventory (error).
- Reports the inventory's completeness limitation explicitly; it never treats missing data from a bounded buffer as proof that an event never existed.
- Exposes immutable issue/result records and aggregate error/warning counts through `kernel.command.events`.

## Safety and limitations

- Validation checks reference integrity and chronology only. It does not prove or disprove root cause.
- `history_complete=True` is a caller assertion; the validator cannot independently prove the inventory is complete.
- Cross-command evidence is a warning, not an automatic rejection, because cross-system evidence may be legitimate when explicitly justified.
- The validator is read-only and does not change the hypothesis registry, event log, command status, or hardware state.

## Verification

- Focused Stage 56 tests: **7 passed**.
- Full test suite: **476 passed**.
- `python3 -m compileall -q kernel tests`: passed.
- AST parse of all kernel Python files: **2,118 files, 0 syntax errors**.
- ZIP integrity: verified after packaging.
