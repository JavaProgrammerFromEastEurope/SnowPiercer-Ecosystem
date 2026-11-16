# TrainOS v104 — release assessment

**Decision: BLOCKED / NO-GO.**

v103 source and evidence are byte-for-byte preserved.
24 functional domains; 954 per-file test modules.

| Acceptance | Result |
|---|---|
| At least 3 complete strict full pytest PASS | True (PASS attempts [1, 2, 5]; FAIL attempts 3 and 4) |
| 3 complete strict joint recovery/CI/diagnostics PASS | True (PASS attempts [1, 2, 3]) |
| Standard ordered serial per-file Kernel Runner | True |
| Opt-in 4-worker per-file Kernel Runner | False |
| Opt-in batch Kernel Runner | True |
| Production PID1/cgroup/cross-UID verified | **False** |

See VERIFICATION_SUMMARY_V104.json, SAFETY_CASE_V104.md and per-attempt logs.
Strict full attempts 3 and 4 failed due to SQLite WAL initialization lock and remain in the evidence.
Four-worker attempt 1 failed two timing-sensitive CI process tests and remains in the evidence.
No result from v101 Codex/v103 is reclassified as a v104 PASS.
Legacy direct runner bypass and supervisor-self SIGKILL keep production status NO-GO.
