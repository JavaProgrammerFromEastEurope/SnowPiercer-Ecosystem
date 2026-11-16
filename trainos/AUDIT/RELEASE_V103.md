# TrainOS v103 — Cumulative Kernel Runner stabilization

**Parent:** TrainOS v102 (`TrainOS-v102-source.zip`); source audit against embedded v101 from `TrainOS_Workspace.zip`.
**Decision:** **BLOCKED / NO-GO**. Release is a development artifact, not a production safety acceptance.

## Scope

- The 24 functional domain names, pinned `legacy_domain_assignments.json`, all legacy test paths and v101/v102 evidence remain available.
- `tests.kernel_runner.runner.KernelTestRunner` retains its public constructor, `run`, `_run_test`, `_run_batch`, `_expand` and `_execute` entry points. The **default** still executes one pytest subprocess per test file, in a fixed order, halting at the first failing file. `TRAINOS_KERNEL_BATCH=1` is unchanged.
- New optional `TRAINOS_KERNEL_WORKERS=2..16` runs *separate pytest processes per file*, with a barrier between functional domains. This opt-in execution changes timing and does not promise serial/fail-immediate semantics within a stage.
- A pytest leader that exits with live same-session descendants returns code **125**, after cleanup; a timeout returns **124**. SIGTERM of a main-thread runner is handled with exit **143** after best-effort process-group cleanup. Direct SIGKILL of a child leader is detected and remaining group members are signaled.
- `scripts/ci/run_with_subreaper.py` is the version preserved in Codex's v101 evidence. It uses Linux `PR_SET_CHILD_SUBREAPER` outside the system's PID 1; it is **not** a privileged production supervisor.
- `scripts/ci/verify_v103.py` supplies bounded evidence for combined regressions, full pytest, default and opt-in worker Kernel Runner, batch mode and stage 83–85 selector. It uses strict warning policies and explicitly injects the existing pytest.ini into nested pytest invocations rather than suppressing configuration warnings.

## Evidence and source audit

- `AUDIT/evidence_v103/BASELINE_INTEGRITY.json` independently hashes **6,720** v101 manifest members and **4,630** v102 manifest members with no mismatches, and verifies both ZIP CRCs. The 2,114 v101-to-v102 deletions are only cache artifacts (`__pycache__` / `.pytest_cache`).
- `AUDIT/evidence_v103/codex_v101_*` is a verbatim selected extract of the *user-supplied* workspace evidence: v101 strict full **1,487 tests** and separately supervised v101 per-file Runner **24 functional domains**, ~251 s. These claims are from archived logs, not an independent v103 execution.
- `AUDIT/evidence_v103/combined_baseline.*`, `combined_1.*`, `combined_2.*` and subsequent unsuccessful records, if any, are retained. The initial strict-global warning policy caused nested pytest in external temporary directories to miss `pytest.ini`, generating pytest-asyncio deprecation failures. `nested_config_probe.*` verifies the actual fix instead of suppressing warnings.
- `AUDIT/evidence_v103/runner_sigkill_boundary.json` records a **negative** safety experiment: external SIGKILL of the Runner leaves its per-file child running; the independent subreaper probe then kills and reaps the child. Full automatic cleanup after runner SIGKILL is **NOT** proven.

## Acceptance gates

See `AUDIT/evidence_v103/VERIFICATION_SUMMARY.json` for completed evidence, exact exit codes and durations, and `AUDIT/evidence_v103/SAFETY_CASE_V103.md` for established versus unproven guarantees. The v103 package retains BLOCKED / NO-GO even when functional and regression tests pass, because independent production-level SIGKILL, cross-UID, cgroups/PID1 and safety integration evidence is unavailable.
