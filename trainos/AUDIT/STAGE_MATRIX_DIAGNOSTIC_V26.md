# Stage Matrix Diagnostic — v26

- Requested range: stages 71–80
- Stage directories found and executed: 10/10
- PASS: 10; FAIL: 0; TIMEOUT: 0
- Pytest cases reported by stage logs: 44 passed
- Aggregate recorded runtime: 35 seconds
- Per-stage timeout: 20 seconds
- Aggregator log validation: PASS (`summarize_stage_results.py --check-logs`)
- Aggregator unit tests: PASS (6 tests)
- Shell regression test: PASS (PASS/FAIL/TIMEOUT classification)
- Archive packaging and integrity checks are recorded in the v26 manifest.

Execution note: the first combined runner invocation was interrupted by the surrounding command time limit while stage 80 was completing. Stage 80 was rerun independently with the same 20-second per-stage timeout and passed (7 tests); its confirmed log and summary were incorporated into the range report. Stages 71–79 passed in the initial run.

## Scope limitations

- Full project test suite: NOT CONFIRMED; the root cause of earlier long-running full-suite attempts remains unresolved.
- Remote GitHub Actions: not executed in this environment.
- Real payment integration: NO_GO pending independent audit and approved policy decisions.
