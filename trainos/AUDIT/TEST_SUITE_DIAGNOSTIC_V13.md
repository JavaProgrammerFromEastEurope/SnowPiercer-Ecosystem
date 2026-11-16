# TrainOS Test Suite Diagnostic v13 — Isolated CI shards

Date: 2026-10-24

## Scope

This stage does not change runtime behavior or financial-ledger semantics. It adds a GitHub Actions workflow that runs the existing test suite in six independent jobs, matching the previously used stage ranges and ledger group. Each job has a 10-minute hard job timeout, and `fail-fast: false` allows all shards to report results even if one fails.

## Fresh diagnostic evidence

- `PYTHONPATH=. python -m pytest --collect-only -q` collected **973 tests** in **1.90 seconds**.
- A fresh verbose monolithic run with the `ddtrace` plugin disabled was still running after 75 seconds and had reached roughly 20% of tests. The process was terminated by the diagnostic timeout. This is evidence of a severe order-/process-sensitive slowdown, but not proof of a deadlock or a specific root cause.
- The previously suspected parameterized case `tests/stage135/test_recovery_owner_identity_consistency.py::test_unknown_or_invalid_pid_cannot_authorize_takeover[0]` passed in isolation: **1 passed in 0.14 seconds**.
- A direct run of `tests/stage130` through `tests/stage140` passed: **28 passed in 8.90 seconds**.
- v12 recorded 973 passes across six separate invocations (70.33 seconds summed). Those results are preserved as prior evidence, not represented as a successful monolithic run.

## CI layout

The workflow `.github/workflows/trainos-tests.yml` defines six independent jobs:

1. stages 1–49
2. stages 50–99
3. stages 100–124
4. stages 125–149
5. stages 150–177
6. `tests/ledger_contract`

The matrix is intentionally non-fail-fast so the whole diagnostic picture remains available. Each shard is independently time-bounded. The workflow has been added to the archive but has **not** been executed on GitHub Actions in this environment; do not treat it as CI validation evidence until a real workflow run completes.

## Conclusion and gate

- Test collection: **PASS**, 973 tests discovered.
- Suspect test in isolation: **PASS**.
- Stage 130–140 shard: **PASS**, 28 tests.
- Historical direct shards: **PASS**, 973 total across separate invocations (v12 record).
- Monolithic suite: **UNRESOLVED / NOT PASSING**; prior run timed out at 300 seconds and fresh run exceeded 75 seconds while at ~20%.
- Root cause: **not established**. Do not describe this as a confirmed deadlock.
- Real-payment integration: **NO-GO** pending reliable CI evidence, full-suite issue resolution, and independent accounting/security review.

## Reproduction

From the canonical `TrainOS/` root:

```bash
PYTHONPATH=. python -m pytest --collect-only -q
PYTHONPATH=. python -m pytest -vv -p no:ddtrace
PYTHONPATH=. python -m pytest -q tests/stage130 tests/stage131 tests/stage132 tests/stage133 tests/stage134 tests/stage135 tests/stage136 tests/stage137 tests/stage138 tests/stage139 tests/stage140
```

For ongoing CI, use `.github/workflows/trainos-tests.yml` and inspect each matrix job separately. Avoid adding retries that silently turn intermittent failures into green status.
