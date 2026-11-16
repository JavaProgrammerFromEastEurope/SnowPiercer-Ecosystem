# TrainOS Stage 98 — Recovery fault sequences and restart boundaries

## Scope

Added fault-sequence tests around the existing startup-recovery workflow. No production recovery behavior was changed: Stage 98 exercises the durable journal and existing fail-closed logic under simulated interruption and explicit retry authorization.

## Invariants tested

1. If candidate publication succeeds but the journal success transition fails, the result remains `BLOCKED` and the attempt stays `IN_PROGRESS`.
2. If the backup checkpoint changes before restart reconciliation, the candidate is not declared ready, the recorded checkpoint remains unchanged, and the candidate is preserved for investigation rather than deleted by pathname.
3. A failed attempt cannot restart automatically. Replacing the backup requires explicit retry authorization bound to the newly reviewed SHA-256 fingerprint; the authorized retry can then complete successfully.

## Validation

- Focused recovery regression suite: `PYTHONPATH=. pytest -q tests/stage98 tests/stage97 tests/stage96 tests/stage95 tests/stage91 tests/stage94` — **16 passed**.
- Full suite: `PYTHONPATH=. pytest -q` — **677 passed in 3.32 s**.
- `python -m compileall -q kernel tests` — passed.
- AST audit — **2,577 Python files, 0 parse errors**.
- ZIP archive integrity — checked separately after archive creation.

This is software fault-injection testing only. It does not establish hardware-in-loop behavior, operational readiness, or safety certification.
