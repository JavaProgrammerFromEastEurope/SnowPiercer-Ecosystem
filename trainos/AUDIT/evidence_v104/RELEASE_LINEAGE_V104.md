# SnowPiercer / TrainOS release lineage and evidence attribution

| Release | Source | Evidence that can be relied upon for this build |
|---|---|---|
| v101 | Historical workspace/Codex report | Reported 1,487 tests and 24 functional domains; not independently reproduced in the v104 execution. |
| v102 | Previous cumulative source/evidence retained within predecessor lineage | Evidence remains part of baseline; v102 statuses are not v104 statuses. |
| v103 | `TrainOS-v103-source.zip` | ZIP SHA-256 `c105dd67a18779ac391c67cbbfe994b3014fbc7318dac996592c428a2af3ba9a`, all 4,761 manifest members verified. Three strict full regressions had passed 1,499 tests in v103, yet standard serial default was interrupted and unconfirmed; leader SIGKILL escape counterexample existed. |
| v104 | Cumulative directory from verified v103 ZIP | Six new supervisor/serial contract tests; 24 functional domains, 954 test modules configured. Full, joint, focused, serial/worker/batch and SIGKILL fanout evidence are collected anew under `AUDIT/evidence_v104`. |

The number of releases is not a readiness metric. A green TrainOS unit suite
is not evidence of independent production cgroup, cross-UID or physical
SnowPiercer readiness. The top-level ecosystem continues in `BLOCKED/NO-GO`
until safety and integration contracts are independently demonstrated.
