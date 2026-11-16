# TrainOS Stage 97 — Event-log recovery integration bench

## Scope

Added an end-to-end integration test bench that exercises the existing event-log trust gate, integrity anchors, verified backup manager, startup recovery, and durable recovery-attempt journal together. This stage deliberately avoids duplicating or rewriting production recovery logic.

## Invariants tested

1. A damaged active event log is rejected by the trust gate; a verified backup can be restored to a separate candidate and the journal records `SUCCEEDED` only after candidate publication and verification.
2. Preparing a candidate never promotes or overwrites the active database. The active log remains damaged and is still rejected after recovery preparation.
3. An invalid/tampered backup fails closed, publishes no candidate, and records a failed attempt.
4. An active log without sufficient anchor evidence is never marked trusted or recovery-ready.

## Validation

Actual validation: `PYTHONPATH=. pytest -q tests/stage97` — 3 passed; full suite `PYTHONPATH=. pytest -q` — 675 passed in 3.19 s; `python -m compileall -q kernel tests` passed; AST audit of kernel and tests — 2,576 Python files, 0 parse errors. This is a software integration test bench, not a hardware-in-loop test and not a safety certification.
