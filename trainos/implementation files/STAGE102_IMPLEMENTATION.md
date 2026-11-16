# TrainOS Stage 102 — Strict Recovery Fencing

## Goal

Close the same-process ownership gap identified during Stage 101: a caller that omits
`owner_run_id` and `fencing_token` must not be able to finish a modern fenced attempt
merely because its PID matches the recorded PID.

## Changes

- `EventLogRecoveryAttemptStore._finish()` now requires both the run UUID and fencing
  token for every attempt created under the fenced schema.
- PID-only completion is retained narrowly for legacy in-progress journal rows that
  have no `owner_run_id`, and only from their recorded process. This preserves a
  migration path for pre-fencing journal entries without weakening modern attempts.
- Existing tests that previously used tokenless completion for new attempts now pass
  the attempt's recorded owner ID and token, reflecting the enforced contract.
- Added tests proving tokenless same-PID completion is rejected and a stale run cannot
  complete a newer operator-authorized retry.

## Validation

- Focused regression suite: `PYTHONPATH=. pytest -q tests/stage102 tests/stage100 tests/stage101 tests/stage99 tests/stage98 tests/stage96 tests/stage95 tests/stage94 tests/stage93 tests/stage90 tests/stage89` — **30 passed**.
- Full suite: `PYTHONPATH=. pytest -q` — **685 passed**.
- `python -m compileall -q kernel tests` — passed.
- AST audit of `kernel/**/*.py` and `tests/**/*.py` — **2,581 files, 0 parse errors**.
- ZIP integrity check — passed.

## Limitations

The token fences journal transitions only. Any external resource or side effect must
independently validate the fencing token to reject stale workers. Legacy rows without a
run UUID retain a narrow PID-only compatibility path; deployments should resolve such
rows deliberately rather than treating PID as a distributed lease. This stage does not
certify TrainOS for real-world train control.
