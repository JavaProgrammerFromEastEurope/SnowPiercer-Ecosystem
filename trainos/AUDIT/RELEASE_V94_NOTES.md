# TrainOS v94 — BLOCKED / NO-GO

Based on v93. Added opt-in sqlite3 owner tracer and real SIGTERM-resistant child SIGKILL contract. No warnings suppressed. Isolated recovery fault tests tracked 15 SQLite connections and found 0 missing explicit closes; the order-dependent warning in combined runs remains unresolved. Three strict combined and full suite runs have no confirmed PASS. Evidence includes failures, interrupted runs, and exit-code files where available. No numbered Stage created.
