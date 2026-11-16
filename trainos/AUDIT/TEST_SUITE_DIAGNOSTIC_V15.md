# TrainOS Test Suite Diagnostic v15 — bounded stage execution

Date: 2026-10-24

## Scope

This release improves test observability and failure containment. It does not change TrainOS runtime code or financial-ledger behavior.

## Change

- Added `scripts/ci/run_stage_matrix.sh` to run each `tests/stageN` in a fresh pytest process.
- Each stage has a configurable hard timeout (default 180 seconds); `timeout` sends TERM and escalates to KILL after 10 seconds.
- Each stage gets a dedicated log and a TSV summary containing stage, status, exit code, elapsed seconds, and log filename.
- The GitHub Actions workflow uploads diagnostic logs even when a stage fails, times out, or is cancelled.
- CI job timeout is 20 minutes; individual stages cannot silently consume the entire job timeout without a stage-level timeout record.

## Local verification

The targeted command `PYTHONPATH=. python -m pytest -q tests/stage117 tests/stage118` completed successfully: **3 passed in 5.95 seconds**.

The runner script was shell-syntax checked and exercised against stages 117–118 with a 30-second timeout. This is a targeted check, not a full-suite result. GitHub Actions has not been run from this environment.

## Important limitations

- The previously observed monolithic slowdown remains unresolved; this release does not claim to identify its root cause.
- Stage isolation is a diagnostic mitigation, not proof of correctness across one monolithic pytest process.
- A stage-level timeout is reported as failure; it must not be interpreted as a passing test.
- Real-payment integration remains **NO-GO** pending independent ledger review, policy decisions for unsupported transaction types, and a fully understood test/CI status.

## Reproduction

```bash
bash -n scripts/ci/run_stage_matrix.sh
PYTHONPATH=. python -m pytest -q tests/stage117 tests/stage118
scripts/ci/run_stage_matrix.sh 117 118 /tmp/trainos-stage-logs 30
cat /tmp/trainos-stage-logs/summary.tsv
```
