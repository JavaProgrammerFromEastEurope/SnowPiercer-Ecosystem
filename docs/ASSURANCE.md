# Assurance boundary and acceptance plan

## Evidence classes

- **A — verified here:** local unit tests, strict warning flags, SHA-256 of emitted artifacts,
  optional independent API probe and seven-direction orchestration compatibility.
- **B — design only:** future signed inter-service commands and MAC integration.
- **C — absent:** four real UIDs, LSM audit rules, delegated cgroups, independent
  witness/permit services, multi-process SIGKILL crash matrix, physical tests.

## Required production gate

All of the following are mandatory and conjunctive: inspected MAC/LSM policy and
actual denial trials; user and group separation; immutable witness/authority roots;
atomic permits; independent supervisor; legacy entrypoint inventory and enforced
fencing; replay/rollback/tamper/crash evidence; hardware safety review; formal
acceptance by authorized owner. Missing **any** keeps `BLOCKED/NO-GO`.

The verification matrix in `evidence/` is a software baseline. It deliberately
includes denied production admission, not a claim of deployed confinement.

## Follow-up functional workstreams (no artificial numbered stages)

`IDENTITY / MAC`, `AUDIT / ANCHOR`, `RECOVERY / PERMITS`, `BROKER / IPC`,
`SUPERVISION / LIFECYCLE`, `SAFETY / INDEPENDENT VERIFICATION`.
Next release candidate: **Security v0.2.0**, contingent on evidence. The next step
should be an OS-enforced broker + confinement design and a reproducible four-UID
harness that remains fail-closed where unavailable.
