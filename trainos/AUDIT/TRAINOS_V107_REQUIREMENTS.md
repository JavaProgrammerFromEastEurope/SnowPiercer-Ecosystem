# TrainOS v107 — Production containment requirements and traceability

This document distinguishes **implemented software** from **verified OS enforcement**.
Production acceptance is **BLOCKED / NO-GO**. A regression PASS cannot override the
absence of independent kernel and service-manager evidence.

| ID | Requirement | Implementation | Confirmed evidence | Outstanding |
|---|---|---|---|---|
| TRN107-REQ-01 | Unique root-owned managed cgroup per admitted run; all exec descendants confined | `cgroup_authority_v106.py` fork gate | Mock admission tests and negative no-delegation probe | Actual attach and escape prevention on delegated cgroup2 |
| TRN107-REQ-02 | Independently restartable OS manager, surviving authority SIGKILL | `cgroup_watchdog_v107.py`, example systemd unit | Single-instance lock unit tests | systemd restart after real SIGKILL authority/watchdog |
| TRN107-REQ-03 | Sweep orphans with real `cgroup.kill`, verify populated=0 before accepting new work | `kill_managed_groups` | Mock sweep and path tamper tests | Actual kernel write, readback and race coverage |
| TRN107-REQ-04 | Fail before exec on missing containment | v106 gate + v107 watchdog checks | Actual denied admission; no marker executed | Positive atomic kernel gate E2E |
| TRN107-REQ-05 | Authenticate peer UID with OS identity, never JSON | `uid_broker_v107.py` SO_PEERCRED | Real cross-UID processes, invalid UID rejection | Operated OS service + privilege separation deployment |
| TRN107-REQ-06 | One-use durable per-UID nonce/replay protection | SQLite `requests` PK(uid, nonce) | 20 concurrent requests, 15 replay denials, replay after server restart | State-bound permit binding to authority's lifecycle |
| TRN107-REQ-07 | OS-protected legacy production writes | Design only; legacy library remains unchanged | Negative bypass confirmed | Privileged write service + restrictive file ACLs and UID namespaces |
| TRN107-REQ-08 | Process identity across PID reuse | pidfd supervisor v105 and authority v106 | Existing pidfd-focused regression and negative controls | Real PID reuse race/cross-process capability audit |
| TRN107-REQ-09 | Crash-consistent recovery at admission and authority restarts | Stateful sweep with exclusive watchdog lock | Lock/sweep mock tests | E2E loss-of-power, concurrent manager restart and group reconciliation |
| TRN107-REQ-10 | Strict multi-run tests with full evidence, including failures | v107 verification runner and archive builder | See actual `AUDIT/evidence_v107` | Must meet complete serial/worker/batch/full matrix thresholds |

## Acceptance rule

`GO = completed strict regression matrix AND fully completed three Kernel Runner
modes AND independently verified OS cgroup/service-manager containment AND
production IPC/write fencing AND signed external safety acceptance`.

No single software unit test or synthetic cgroup directory satisfies the last three gates.
