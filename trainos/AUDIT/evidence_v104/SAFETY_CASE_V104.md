# TrainOS v104 — Linux process containment safety case

**Decision: BLOCKED / NO-GO.** No production certification is claimed.

## Scope and predecessor

The v103 archive was independently checked against its published SHA-256; all
4,761 members of the v103 internal manifest were verified against ZIP content
and the extracted v104 workspace byte-for-byte before new files were added.
The original v103 Kernel Runner remains intact, including its public method
signatures and strict ordered per-file `pytest` subprocess behavior. This v104
release adds an **external** process supervisor, rather than silently
replacing the legacy runner with batched or worker-mode semantics.

## Safety requirements

- `S-104-01` MUST fail closed if Linux `/proc` or `PR_SET_CHILD_SUBREAPER` is unavailable.
- `S-104-02` MUST place the runner in a new POSIX session and be a distinct living parent.
- `S-104-03` MUST adopt/reap process descendants on runner death, including detached `setsid()` children.
- `S-104-04` MUST signal live adopted descendants with TERM, escalate to KILL, then verify non-running state.
- `S-104-05` MUST return `137` when the runner is killed by SIGKILL and cleanup succeeds; MUST NOT report a PASS.
- `S-104-06` MUST return `125` on observed residual processes or when runner exits zero leaving detached orphan processes, even if cleanup succeeds.
- `S-104-07` MUST forward SIGTERM and INT to a living runner and provide bounded escalation, then return `128+signal`.
- `S-104-08` MUST enforce an external timeout with code `124`, separate from per-file runner timeout.
- `S-104-09` MUST leave serial default, per-file subprocesses, ordered fail-fast and 24 domain boundaries intact.
- `S-104-10` MUST retain every failed and incomplete evidence attempt. Missing evidence is NOT_EXECUTED, never PASS.

## Implementation

`python -m scripts.ci.process_supervisor_v104 --report REPORT -- python -m tests.kernel_runner`

Linux `prctl(PR_SET_CHILD_SUBREAPER)` is set before runner spawn. The supervisor
periodically observes `/proc` parent relationships, records process start ticks
as a basic defense against PID reuse, and reaps adopted children with `waitid`
and `waitpid`. The supervisor, not the runner, handles child cleanup after
SIGKILL of the runner. It uses real Linux signals; no mock is substituted for
the subprocess boundary checks.

## Explicitly unresolved assumptions and counterexamples

1. **Supervisor SIGKILL**: fatal loss of the independent supervisor bypasses
   Python cleanup. A separate OS supervisor / cgroup v2 service boundary is
   needed; this is NOT certified.
2. **PID reuse / procfs TOCTOU**: validating `/proc/PID/stat` immediately before
   `kill(PID)` reduces but does not eliminate races between validation and kill.
   Production requires pidfds / kernel-enforced cgroups, with tests under PID reuse pressure.
3. **Cross-UID**: no independent cross-UID enforcement demonstrated. Processes
   running as a UID which this supervisor cannot signal are fail-closed but not
   guaranteed to be terminated.
4. **cgroup containment**: the current container mounts cgroup v2 read-only;
   no delegated writable cgroup, `cgroup.kill` or production service manager
   operation has been proved. The process supervisor is not a security sandbox.
5. **PID 1**: `supervisord` is PID 1 in the verification container, not a
   verified TrainOS production init; the subreaper specifically prevents
   adoption of supervised descendants by that PID 1 during normal operation.
6. **Concurrent malicious writers / hostile processes**: this is cooperative
   process cleanup, not an arbitrary executable isolation authority.
7. **One remaining legacy entrypoint**: direct invocation of
   `python -m tests.kernel_runner` bypasses the independent supervisor.
   This preserves API compatibility but cannot be approved as mandatory
   production admission.
8. **Host-specific performance**: full 954-file serial test execution may take
   longer than batch or opt-in worker mode. Batch/worker PASS is never
   substituted for serial completion. A timed-out or manually terminated
   serial run remains incomplete.
9. **Physical and system integration**: TrainOS unit and process tests do not
   establish readiness of Rail Systems, Energy, Life Support or SnowPiercer
   Island or certification of the SnowPiercer ecosystem.

## Evidence standard

Every verification attempt has unique `<case>_<iteration>.json`, `.exitcode`,
`.stdout.log` and `.stderr.log` artifacts. The independent supervisor
additionally creates `<case>_<iteration>.supervisor.json` when used. Source
SHA-256 hashes in each report bind results to source revision; exit=0 and
complete logs are required for PASS. The cumulative archive manifest verifies
all included files; its hash is published separately.

## Additional independent OS-boundary probes

`CGROUP_PID1_PROBE_V104.json`: attempted cgroup directory creation returned
`EROFS` (read-only filesystem), exit 1. `PID_NAMESPACE_PROBE_V104.json`:
`unshare --pid --fork --mount-proc true` returned `EPERM` (operation not
permitted), exit 1. These two negative results prevent production claims of
cgroup enforcement or independent PID namespace/PID1 isolation in this environment.

`TERM_ESCALATION_PROBE_V104.json` records a separate real process which
ignored SIGTERM: the supervisor escalated to SIGKILL, reported its root's
negative wait status `-9`, returned wrapper code `143` and observed no live
remaining descendants. This tests bounded escalation but does not cover
killing the supervisor itself.

`ACTUAL_KERNEL_SIGKILL_V104.json` is a stronger, independent end-to-end
probe. A real `python -m tests.kernel_runner` was launched inside the external
supervisor. While it had a real per-file pytest child, the Runner received
SIGKILL. The supervisor returned 137 and reported `cleanup_complete=true`;
the observed pytest child was no longer running. This verifies this exact
crash boundary on this Linux host, not generic PID1/cgroup certification.
