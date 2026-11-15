# RAIL-TRUST-006 — End-to-End Recovery Fencing & Production Boundary Hardening

Status: **PARTIAL / NO-GO**. This is an experimental same-UID Unix socket boundary, not an independently audited production service.

## Requirements and contracts

- RAIL-TRUST-006-R01: fail closed if independent anchor provider is missing or inconsistent.
- R02: startup preflight must acquire the same admission.lock as unified admission/recovery; reject PREPARED state.
- R03: socket must be owner-controlled, mode 0600; refuse existing socket paths, including symlinks; never unlink replaced paths.
- R04: verify SO_PEERCRED (Linux only), refuse cross-UID peers; unsupported platforms fail closed.
- R05: the only recognized IPC verb is ADMIT, delegating to unified_admission.admit; no legacy unsigned release gate.
- R06: invalid attestation, missing external provider, or active recovery fence cannot produce PASS.
- R07: preserve previous library APIs and existing Stage tests.

## Safety analysis

A socket identity check before accept and after accept reduces pathname substitution exposure but cannot authenticate an already-open socket's provenance across all namespace attacks. Startup preflight releases the lock before serving: it is not an atomic startup/admission transaction. Peer UID is insufficient against same-UID malicious code. The independent monotonic provider is not bundled; a mock is not evidence of tamper resistance. A single-request blocking service has no request size framing beyond 256 bytes, no supervisor, no cancellation protocol and no service-level recovery authorization.

## Evidence scope

Unit tests cover fail-closed startup, PREPARED startup fencing, socket path replacement, unsupported IPC verbs and invalid attestation. Cross-UID, SIGKILL at every boundary, power-loss, durable external CAS and physical system integration are NOT established. Existing legacy library entrypoints remain callable, so complete elimination of bypass paths is NOT demonstrated.

## Acceptance

Software-only tests may PASS; production admission and physical railway operation remain **BLOCKED / NO-GO** until independently tested end-to-end recovery and privileged boundary design are delivered.
