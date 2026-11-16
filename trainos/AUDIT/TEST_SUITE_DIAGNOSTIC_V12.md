# TrainOS Test Suite Diagnostic v12

Date: 2026-10-24

## Results

A monolithic `PYTHONPATH=. python -m pytest -q --durations=30` run timed out after 300 seconds at approximately 16% progress. Repeating with `-p no:ddtrace` also timed out near the same point. The verbose log stopped during `tests/stage123/test_retry_limit_survives_repeated_crashes.py::test_repeated_crash_cannot_exceed_max_attempts_after_restart`.

The implicated test passed in isolation and in an explicit prefix of 166 collected test cases. Relevant neighboring recovery stages also passed in isolated runs. This is not enough to identify a single root cause.

All 973 collected tests passed in six independent direct pytest invocations:

| Group | Result | Duration |
|---|---:|---:|
| Stages 1–49 | 439 passed | 2.25 s |
| Stages 50–99 | 240 passed | 4.19 s |
| Stages 100–124 | 62 passed | 22.56 s |
| Stages 125–149 | 78 passed | 14.67 s |
| Stages 150–177 | 90 passed | 20.47 s |
| `tests/ledger_contract` | 64 passed | 6.19 s |
| **Total** | **973 passed** | **70.33 s summed across runs** |

The results above came from separate direct pytest commands and each command exited successfully. A later attempt to automate the grouping in a shell wrapper intermittently stalled after earlier groups passed, while the affected stage range passed again when run directly. This strengthens the suspicion of an order-/process-environment-sensitive interaction, but the exact cause remains unresolved.

## Reproduction commands

Run these commands directly from the canonical `TrainOS/` root, one invocation at a time. Keep the outputs and exit codes; do not infer success from partial progress output.

```bash
PYTHONPATH=. python -m pytest -q --durations=20 $(for i in $(seq 1 49); do [ -d tests/stage$i ] && printf 'tests/stage%s ' "$i"; done)
PYTHONPATH=. python -m pytest -q --durations=20 $(for i in $(seq 50 99); do [ -d tests/stage$i ] && printf 'tests/stage%s ' "$i"; done)
PYTHONPATH=. python -m pytest -q --durations=20 $(for i in $(seq 100 124); do [ -d tests/stage$i ] && printf 'tests/stage%s ' "$i"; done)
PYTHONPATH=. python -m pytest -q --durations=20 $(for i in $(seq 125 149); do [ -d tests/stage$i ] && printf 'tests/stage%s ' "$i"; done)
PYTHONPATH=. python -m pytest -q --durations=20 $(for i in $(seq 150 177); do [ -d tests/stage$i ] && printf 'tests/stage%s ' "$i"; done)
PYTHONPATH=. python -m pytest -q --durations=20 tests/ledger_contract
```

## Interpretation and gate

- Grouped testing: **all 973 tests passed** in one set of direct grouped runs.
- Monolithic suite: **not passed**; it timed out and its process/order interaction remains unresolved.
- Automated wrapper: **not adopted** because its own run was intermittent.
- Production gate: **NO-GO** for real payment integration until the monolithic hang and process cleanup behavior are understood, repeatable CI is established, and security/accounting reviews are complete.
