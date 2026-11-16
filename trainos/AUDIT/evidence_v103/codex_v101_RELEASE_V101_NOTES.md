# TrainOS v101 — SQLite Owner Teardown & Full Strict Validation

**Base:** cumulative v100. **Decision:** BLOCKED/NO-GO (conservative).

## Verified root cause

Tests in stage83, stage84 and stage85 created 23 SQLite-backed stores without guaranteed explicit close. Their lifetime was left to garbage collection, making later pytest tests report order-dependent `PytestUnraisableExceptionWarning`. Three test files now use teardown-owned store fixtures. The original v100 strict full run reported 23 warnings and failed. After the fixes, the strict full run passed. This strongly supports the causal link; the original owner-tracing attempt timed out and is not presented as independent confirmation.

No production SQLite behavior was changed. Warning filters remain strict.

## Validation

- Strict combined recovery + ci_release + pytest_diagnostics: three completed runs, 397 passed each, exit 0, bounded group absent.
- Strict full after SQLite fix: 1485 passed, exit 0.
- Final strict full after adding kernel batch contracts: 1487 passed, exit 0.
- Strict process contracts: 9 passed, exit 0.
- Affected 13 tests: 13 passed, exit 0.
- Regression selector stages 83–85: 13 passed, exit 0.
- Full Kernel Runner: opt-in `TRAINOS_KERNEL_BATCH=1` passed all configured functional stages, exit 0. Original per-file full Kernel Runner was terminated with exit 143 before completion. Both logs retained.
- Kernel Runner batch compatibility contracts: 2 passed, exit 0.

## Safety and limitations

`TRAINOS_KERNEL_BATCH=1` is opt-in; original per-file runner remains default. A batch can expose cross-test order effects not seen with per-file execution. Successful batch and full strict suite are separate evidence. Bounded runner group-absence checks cover its managed process groups; global absence of every possible orphan cannot be proven from this environment. The original source owner trace did not finish. No warning suppression was added.

## Evidence

`AUDIT/evidence_v101/` contains stdout, stderr, exit codes, bounded JSON reports, timeout attempts, process tests, Kernel Runner, selector and owner diagnostic records. `AUDIT/SHA256_MANIFEST_V101.json` hashes all archive members except itself.
