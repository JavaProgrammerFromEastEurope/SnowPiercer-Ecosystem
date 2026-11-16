# TrainOS Test Suite Diagnostic v14 — Per-stage process isolation

Date: 2026-10-24

## Objective

Reduce cross-stage test-process interactions while gathering better evidence about the unresolved monolithic pytest slowdown. This release changes test orchestration only; it does not change TrainOS runtime code or financial-ledger semantics.

## Fresh observations

- A fresh verbose monolithic run reached the stage 118 test after reporting a failure in one parameter of the stage 117 crash-boundary test. The run did not complete within the outer diagnostic window. The last visible test was `tests/stage118/test_expired_lease_recovery_contention.py::test_expired_lease_cannot_be_resurrected_and_only_one_retry_owner_wins`.
- The exact stage 117 parameter that appeared failed in the combined run passed when rerun alone: `1 passed in 0.92s`.
- Stage 118 passed alone: `1 passed in 3.30s`.
- Combined stages 117 and 118 passed in three consecutive invocations: `3 passed` each (4.27s, 5.82s, 5.81s).
- These observations establish an order-/environment-sensitive symptom, but do not establish a root cause. The first monolithic run output included a transient failure; subsequent isolated and combined reproductions passed.

## CI adjustment

The stage-shard workflow now runs each existing `tests/stageN` directory in a fresh pytest process rather than one process for an entire 25–50 stage shard. The six jobs and 10-minute per-job timeout remain. Failures are accumulated across stages so a failure in one stage does not prevent later stages in the same job from reporting results. The workflow is authored but has not been executed on GitHub Actions here.

This isolation strategy is a diagnostic mitigation, not proof that the underlying cause is fixed. Per-stage runs also mean the full suite has not been validated as a single pytest process.

## Status

- Collection: previously confirmed 973 tests.
- Stage 117 crash-boundary case: isolated pass after transient combined-run failure.
- Stage 118 contention case: isolated pass.
- Stages 117–118 together: 3 consecutive passes.
- Monolithic suite: unresolved; no full successful run claimed.
- GitHub Actions: workflow not executed in this environment.
- Real-payment integration: NO-GO.

## Reproduction

```bash
PYTHONPATH=. python -m pytest -vv -p no:ddtrace
PYTHONPATH=. python -m pytest -q tests/stage117 tests/stage118
PYTHONPATH=. python -m pytest -q tests/stage117/test_lease_renewal_process_crash.py::test_restart_reconciles_lease_state_after_process_crash\[after_commit-75-True\]
PYTHONPATH=. python -m pytest -q tests/stage118/test_expired_lease_recovery_contention.py
```
