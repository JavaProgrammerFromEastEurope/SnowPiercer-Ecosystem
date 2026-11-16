# TrainOS v82

Migrated ten recovery schema tests into a functional domain. Added explicit pytest-asyncio fixture loop scope, last-resort SQLite connection finalizer, and two migration contracts. Three strict migrated-module regressions passed. The strict full recovery domain did not pass: 3 failures from unclosed sqlite connections. No full-suite or hosted CI acceptance is claimed.
