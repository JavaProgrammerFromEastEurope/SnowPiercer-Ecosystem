# Proposed TrainOS v106 — independent OS process containment and production admission

**Starting state: v105 BLOCKED/NO-GO, even if strict software regression is green.**

## Objective
Eliminate the demonstrated counterexample in which killing the v105 supervisor leaves a Runner and detached descendant executing. A subreaper in the same process does not survive its own SIGKILL.

## Functional acceptance
1. Dedicated OS-managed cgroup v2 scope with a verified writable delegation, created before subprocess admission and covered by an independent OS watcher (systemd/launchd/service manager with a documented, tested Linux mode).
2. Put every workload process inside a scope *before exec*, verify membership and creation-time identity, use cgroup.kill during recovery, and prove cleanup when killing both Runner and supervisor under load; preserve fail-closed status when authority is unavailable.
3. Replace remaining unguarded numeric PGID operations with cgroup-scoped control and pidfds; test PID reuse, fast fork/exec, setsid, double-fork, orphan adoption and competing SIGTERM/SIGKILL.
4. OS-enforced production admission, not a mutable environment flag. Show legacy direct Runner cannot cross UID, filesystem, IPC or cgroup boundaries; test negative cases using actually distinct UID credentials.
5. Resolve any remaining SQLite contention and demonstrate stable repeated strict serial/worker/batch modes without weakening warnings, per-file isolation, stage barrier or fail-fast.
6. Preserve API and all historical evidence; independently verify process containment and cgroup manager permissions outside the development container. Production approval remains NO-GO until those proofs exist.

## Non-claims
Successful test collection, operation of a PIDFD or read-only cgroup2 mount does **not** constitute proof of OS-enforced production process containment. No hardware, safety-critical control or cross-subsystem end-to-end certification is inferred from TrainOS unit and integration tests.
