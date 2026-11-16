# TrainOS v106 — independent process containment architecture

**Release status: BLOCKED/NO-GO.** Reference implementation and fail-closed tests are not cgroup-certification evidence. The core, 24 functional areas and all prior evidence are cumulative.

## Purpose and trust boundaries

The **authority** (`scripts/ci/cgroup_authority_v106.py`) is a root-owned lifecycle service, separate from and outside the test-run cgroup. It is not the Runner and not the v105 supervisor. A system service manager must keep the authority alive beyond the supervisor; `SIGKILL` of the authority itself remains an explicitly out-of-scope unproved boundary.

```
Independent PID 1 / OS service manager [NOT DEPLOYED HERE]
    └── privileged lifecycle authority (outside target cgroup)
         ├── pidfd identity of supervised child
         ├── delegated, root-owned cgroup-v2 root [NOT AVAILABLE HERE]
         │     └── private run cgroup (membership before exec)
         │           └── v105 supervisor (service UID)
         │                 └── Runner -> pytest / setsid / double-fork children
         └── cgroup.kill; wait cgroup.events populated=0; remove run cgroup
```

## Contract v106

1. **Pre-exec admission:** before `exec`, a forked process blocks on an anonymous pipe. Authority opens its pidfd, writes numeric PID to `cgroup.procs`, verifies membership, then releases exactly one gate byte. Failure closes gate and ends child without executing the command.
2. **Identity:** root child is pinned by pidfd and retained as a direct waitpid child. Once in cgroup, `cgroup.kill` targets kernel cgroup membership, not a potentially recycled PID or PGID. v105 development supervisor retains earlier per-PID assumptions and is not itself a production security boundary.
3. **OS-enforced containment:** production requires a root-owned, non-world/group-writable delegated cgroup-v2 subtree, real `statfs` cgroup2 magic, `cgroup.procs`, `cgroup.kill`, and a successful test directory creation. Environment credentials and `/tmp` cgroup emulators are NOT permitted.
4. **UID separation:** authority UID 0, supervisor/service UID nonzero, client UID nonzero and different. Actual authorization of individual client requests is not implemented or certified; the CLI checks values, not peer credentials. Filesystem ACLs and IPC peer authentication remain mandatory external work.
5. **Cleanup:** after child/supervisor exit, timeout or handled termination, authority writes `1` to `cgroup.kill`, checks `cgroup.events` for `populated 0`, and removes the per-run group. Errors cause fail-closed code `125` and are recorded. `SIGKILL` of the authority can bypass this cleanup absent OS-manager control.
6. **Fail-closed production:** without delegated cgroup, explicit `--production`, distinct UIDs and permitted trusted supervisor command, no service process is launched. Existing `KernelTestRunner` APIs are unchanged and remain development interfaces; legacy same-UID direct invocation is NOT OS-fenced.
7. **Warning policy:** all strict pytest cases use errors for `ResourceWarning`, `DeprecationWarning`, `pytest.PytestUnraisableExceptionWarning`; kernel cases receive `PYTHONWARNINGS` and the existing `pytest.ini`.

## Required independent certification environment

- Linux kernel supporting writable delegated cgroup v2, `cgroup.kill`, pidfd, and `cgroup.events`; root-controlled service unit with `Delegate=yes` / appropriate delegation policy; protect control directory against client and supervisor writes.
- Dedicated client UID, service UID, privileged authority UID, and independent watchdog UID. Verify peer-credential-authenticated IPC (e.g. `SO_PEERCRED`) and immutable/independently anchored production state, not env tokens alone.
- Deploy authority under a real OS service manager with documented restart + leftover cgroup sweep. Verify supervisor and authority SIGKILL independently. Do not kill PID 1 or perform these experiments on production infrastructure.
- Exhaustive fault injections: immediately before fork, after pidfd open, before/after cgroup.procs, before/after gate release, after double-fork/setsid, before/after `cgroup.kill`, during `cgroup.events`, and on cleanup/restart; verify no running process escaped, including under changing UIDs.
- Verify cgroup ancestor delegation, migration/escape permissions, PID reuse and cgroup name replay, malicious symlinks and mounts, concurrent admission, direct legacy execution, timeouts, service manager restart, and reboot.
- Independently attest command hashes, filesystem permissions, executable paths, read-only runtime images, and broker credentials. CLI command-shape checking is NOT attestation.

## Known limitations

This container has a read-only cgroup v2 mount (EROFS), no delegated subtree and PID 1 is `supervisord`. The real positive `cgroup.kill` path and cross-UID OS fencing cannot be exercised here. The v106 synthetic `_kill_and_verify` tests are **unit-only**. A real independent-subaper probe confirms that SIGKILL of v105 supervisor leaves Runner and double-fork grandchild alive until the external probe intervenes. A passing software regression does not imply TrainOS production safety, railway certification or financial readiness.
