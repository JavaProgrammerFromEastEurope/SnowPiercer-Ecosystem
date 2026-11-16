# TrainOS v103 — final release assessment

**Decision: BLOCKED / NO-GO.**

| Acceptance check | Result |
|---|---|
| 24 domain registry | 24 domains, 953 test files |
| Three complete strict full regressions | PASS |
| Three final strict joint regressions | PASS |
| Default strictly serial Kernel Runner | NOT COMPLETED |
| Opt-in 4-worker per-file Kernel Runner | PASS |
| Opt-in batch Kernel Runner | PASS |
| Automatic cleanup after SIGKILL of Runner | **FAIL: counterexample confirmed** |

## Exact completed runs

- `combined_1`: FAIL, exit=1, duration=54.975 s
- `combined_2`: FAIL, exit=1, duration=57.499 s
- `combined_3`: PASS, exit=0, duration=64.041 s
- `combined_4`: PASS, exit=0, duration=63.441 s
- `combined_5`: PASS, exit=0, duration=61.1 s
- `combined_6`: PASS, exit=0, duration=61.532 s
- `combined_7`: PASS, exit=0, duration=56.906 s
- `combined_8`: PASS, exit=0, duration=58.01 s
- `strict_full_2`: FAIL, exit=1, duration=115.146 s
- `strict_full_3`: PASS, exit=0, duration=142.742 s
- `strict_full_4`: PASS, exit=0, duration=138.972 s
- `strict_full_5`: PASS, exit=0, duration=135.699 s
- `selector_2`: PASS, exit=0, duration=4.236 s
- `selector_3`: PASS, exit=0, duration=4.173 s
- `kernel_default_1`: FAIL, exit=143, duration=125.583 s
- `kernel_default_2`: FAIL, exit=143, duration=243.731 s
- `kernel_workers_1`: PASS, exit=0, duration=766.351 s
- `kernel_batch_1`: PASS, exit=0, duration=196.012 s

Failed or interrupted runs are preserved, not silently discarded.
Source integrity and checksums: BASELINE_INTEGRITY.json and SHA256_MANIFEST_V103.json.
See SAFETY_CASE_V103.md and FAILURE_TRIAGE_V103.md for limitations and root causes.
