# TrainOS Stage 61 — Investigation closure aggregation

## Implemented

- Added `DiagnosticInvestigationClosureReporter`, a read-only aggregate over the existing task tracker snapshot, hypothesis registry snapshot, and Stage 60 closure verification report.
- Added immutable `InvestigationHypothesisSummary` and `DiagnosticInvestigationClosureReport` records.
- Summarizes task states and closure outcomes per hypothesis, includes outstanding task IDs and finding codes, and provides explicit next-step recommendations.
- Distinguishes blocked investigations, open tasks, review-required cases, hypotheses without planned tasks, and cases ready for independent expert review.
- Requires a complete event history and explicit `evidence_supports` / `evidence_refutes` disposition before reporting `ready_for_expert_review`.
- Reports tasks referring to absent/evicted hypotheses as orphans rather than silently dropping them.
- Rejects mismatched closure/task inventories and duplicate task or hypothesis identifiers.
- Exported the new public types from `kernel.command.events`.

## Safety and limitations

- Read-only: no task transitions, hypothesis disposition changes, evidence retrieval, or command execution.
- `ready_for_expert_review` is not a causal root-cause verdict, confirmation of remediation, or authorization to operate equipment.
- Completeness is inherited from the supplied Stage 60 closure report and cannot independently establish that the caller's event history is authoritative.
- Existing trackers and registries remain in-memory components.

## Verification

- Focused Stage 61 tests: **8 passed**.
- Full test suite: **509 passed**.
- `python3 -m compileall -q -x '(/\\.venv/|/\\.history/|/__pycache__/|/node_modules/)' kernel tests`: passed.
- AST parse of all kernel Python files: **2,123 files, 0 syntax errors**.
- ZIP integrity: checked after archive creation.
