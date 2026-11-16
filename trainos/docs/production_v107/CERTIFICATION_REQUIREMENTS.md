# TrainOS v107 production boundary — certification requirements

**Decision: BLOCKED / NO-GO. No production acceptance without external E2E evidence.**

## Architecture / contract

- An independently launched, OS-owned `trainos-watchdog-v107.service` stays OUTSIDE
  the managed runner cgroup and is restarted by systemd after SIGKILL. Startup
  **must** sweep all matching stale run cgroups with kernel `cgroup.kill` and
  verify `cgroup.events: populated 0` before new admission. Watchdog also holds
  an exclusive root-owned lock for the whole lifetime.
- `cgroup_authority_v106` holds the `fork -> blocked pipe -> attach via cgroup.procs
  -> confirm membership -> release exec` gate. Child inherits containment through
  `setsid` and `double-fork` *if* no migration capability is conferred.
- Managed cgroups are root-owned 0700, under a root-owned delegated subtree,
  which is writable only by the trusted authority. Untrusted service/client UIDs
  must not have `CAP_SYS_ADMIN`, `CAP_SYS_RESOURCE`, delegated subtree write,
  or access to cgroup migration control files. Privileged root is a trusted
  authority, not an adversary handled by this design.
- v107 Unix IPC broker uses **kernel SO_PEERCRED**, records one-use per-UID nonces
  in a protected SQLite database and denies unknown UIDs, replay, impersonated UID.
  **The broker is deny-only** pending an independently verified request->watchdog
  IPC handoff, state-bound authorization and OS-enforced legacy file ACLs.
- Existing `KernelTestRunner` library APIs remain callable for development; this
  is deliberately NOT a proven production fence. Environment variables are
  untrusted flags, not security credentials.

## Deployment and evidence prerequisites

1. Linux host with real writable delegated cgroup2 subtree, real `cgroup.kill`,
   root-controlled migration permissions and independently managed systemd PID1.
2. Unit installed with absolute verified Python binary, module path, dedicated
   non-root service UID and separate client UID; hardened `systemd-analyze security`
   results; validated `Restart=always` after SIGKILL watchdog.
3. Authenticate requests via SO_PEERCRED across actual UIDs; durable replay journal
   and monotonic state transitions with concurrent restart. Tested refusal after
   tamper/rollback or journal corruption.
4. Positive end-to-end request -> per-run cgroup before exec -> supervisor/Runner
   -> actual crash at each boundary -> independent watchdog recovery. Observe
   `cgroup.procs`, `cgroup.events`, `cgroup.kill` on real cgroupfs, not temporary
   directories or mock adapters.
5. On a real managed host, SIGKILL Runner, supervisor, authority, and watchdog
   independently; verify no *running* descendants after OS restart; include
   detached descendants, setsid, double-fork, concurrent attempts and PID reuse.
6. Prove OS-managed ledger/store write restrictions stop direct legacy production
   writes. This v107 software alone does **not** enforce that restriction.
7. Independently audit safety/failure evidence; no payment, rail, energy,
   life-support or physical integration GO inferred from Python test success.

## Observed constraints / residual risks

- The execution container reports cgroup v2 **read-only** and PID1 `supervisord`.
  Positive kernel `cgroup.kill`, service restart, migration defense and real
  production admission cannot be demonstrated here.
- A watchdog killed while systemd is unavailable leaves a real interval in which
  descendants can continue running. A watchdog process cannot defend its own
  SIGKILL without an external OS manager.
- Cross-UID SO_PEERCRED protects the identity on an IPC socket, but does not
  prevent same-UID legacy API use, nor verify hardware safety.
- `pidfd` binds observed direct process identity; without cgroup it does not
  close detached-descendant gaps, and does not remove all file descriptor or
  filesystem race opportunities.
- The included systemd unit is a deployment **template deliberately blocked**
  with invalid UIDs and missing command. It is NOT evidence of installation.
