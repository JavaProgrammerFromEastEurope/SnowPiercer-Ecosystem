# TrainOS Stage 52 — Cross-execution diagnostic patterns

## Implemented

- Added `ExecutionDiagnosticPatternAnalyzer`, a deterministic, read-only analyzer over the existing bounded `ExecutionDiagnosticSnapshot`.
- Detects diagnostic codes observed in at least two distinct execution IDs, keeping within-execution repetition separate from cross-execution correlation.
- Each `CrossExecutionDiagnosticPattern` includes sorted execution IDs, distinct execution count, retained occurrence count, first/last timestamps, severity, priority, and a conservative investigation recommendation.
- Critical severity takes priority; otherwise patterns spanning at least three executions or containing repeated occurrences receive high investigation priority.
- Timestamps are validated as ISO-8601 values with timezone information before comparisons.
- Exported the new public types from `kernel.command.events` and added five focused tests.

## Safety and limitations

- A shared diagnostic code is correlation evidence, not proof of a common root cause.
- The analysis is limited to currently retained monitor groups; it is not durable lifetime analytics and can be affected by bounded retention.
- The analyzer does not mutate the event stream, audit ledger, execution status, or execute commands. It is not a safety decision or a hardware-control component.

## Verification

- Focused Stage 52 tests: **5 passed**.
- Full test suite: **453 passed**.
- `python3 -m compileall -q kernel tests`: passed.
- AST parse of all kernel Python files: passed (2114 files, 0 syntax errors).
- ZIP integrity: passed after archive creation.
