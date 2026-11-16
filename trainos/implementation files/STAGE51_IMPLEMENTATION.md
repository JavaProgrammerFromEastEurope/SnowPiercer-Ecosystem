# TrainOS Stage 51 — Diagnostic pattern analysis

## Implemented

- Added `ExecutionDiagnosticAnalyzer`, a deterministic, read-only analyzer for `ExecutionDiagnosticSnapshot`.
- Added immutable `DiagnosticAnalysis` and `DiagnosticRecommendation` result records and exported them from the existing events package.
- Summarizes retained diagnostic groups by code, repeated groups, and repeated occurrences.
- Produces investigation guidance for the known execution-audit integrity codes and a conservative generic recommendation for unknown codes.
- Prioritizes critical findings first; repeated non-critical findings receive higher investigation priority. A repeated critical finding remains critical.
- Repeated findings are explicitly framed as a reason to investigate timelines/common causes, not proof of root cause. The analyzer does not mutate the audit ledger, monitor, execution status, or execute commands.

## Scope and limitations

- Analysis is limited to the monitor snapshot's currently retained groups. It is not durable lifetime analytics; Stage 50's bounded-retention behavior remains unchanged.
- Recommendations are deterministic triage guidance, not an automated root-cause determination, remediation plan, or safety decision.
- This work does not authorize TrainOS to control real train hardware.

## Verification

- Focused Stage 51 tests: **4 passed**.
- Full test suite: **448 passed**.
- `python3 -m compileall -q kernel tests`: passed.
- AST parse of all **2,113** kernel Python files: **0 syntax errors**.
- Archive integrity: checked after packaging.
