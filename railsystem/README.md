# RailSystem — SnowPiercer Ecosystem

RailSystem is the rail-domain subsystem of SnowPiercer. This repository is an **initial architectural scaffold**, not a railway-certified control system.

## Scope
Rolling stock, track/infrastructure, traffic operations, signaling/safety interfaces, traction/braking, maintenance, digital twin and rail operations.

## Integration
TrainOS is an external platform dependency. No TrainOS v80 files are modified. Interfaces are versioned and fail closed for safety-critical requests.

## Development gates
1. Requirements and hazard register
2. Interface contracts and simulation
3. Unit and integration verification
4. Hardware-in-the-loop and independent safety assessment
5. Regulatory authorization before operational deployment

Run: `python -m unittest discover -s tests -v`

## v0.2 / RAIL-ARCH-001
Machine-readable registry: `architecture/registry.json`; validator: `railsystem/architecture.py`; evidence: `docs/RAIL-ARCH-001.md`. Run tests: `python -m unittest discover -s tests -v`. All interfaces are conceptual and non-actuating.

## v0.3 / RAIL-REQ-001
Requirements registry and traceability validator: `requirements/registry.json`, `railsystem/requirements.py`. All requirements are **proposed**, none verified. See `docs/RAIL-REQ-001.md`.

## v0.4 / RAIL-SAFE-001
Preliminary hazard log: `safety/hazards.json`; validator and report: `railsystem/safety.py`; tests: `tests/test_safety.py`. All six hazards open, likelihood unknown, operational authorization false. No safety certification or live control.

## v0.5 / RAIL-IF-001
Versioned, read-only TrainOS boundary prototype: `interfaces/trainos_v1.json`, `railsystem/integration.py`, `tests/test_integration.py`. No connection to TrainOS, no hardware access and no executable commands. See `docs/RAIL-IF-001.md`.

## v0.6 / RAIL-SIM-001
Isolated deterministic 1D simulation prototype: `railsystem/simulation.py`, `tests/test_simulation.py`, `docs/RAIL-SIM-001.md`. This simplified model is **not** validated for real train control or braking safety.

## v0.7 — RAIL-OPS-001

Added `railsystem.operations` for isolated virtual network and timetable planning.
See `docs/RAIL-OPS-001.md`. All results are simulation-only; no dispatch or movement authority is provided.

## v0.8 — RAIL-VER-001
Run all tests: `python -m unittest discover -s tests -v`.
Generate evidence (from project root):
`python -m railsystem.verify_cli --output ../RailSystem_v0.8_evidence.json`
The report contains a SHA-256 source manifest, test results, and a stage-to-test-file mapping. Reports must be written outside the project source tree. CI configuration and independent review remain pending.

## RAIL-CI-001
Run `python -m railsystem.release_cli --output ../release-gate.json`; without approved external baseline status is BLOCKED (exit code 2).

## v0.21 — RAIL-TRUST-011
Added a Linux cross-UID recovery-broker *library* and a fail-closed independent permit-consumption interface. No production external services are provisioned. Legacy library interfaces remain importable; they are not approved production routes. See `docs/RAIL-TRUST-011.md`. Production BLOCKED; physical rail operation NO-GO.

## v0.22 — RAIL-TRUST-012
Linux OS peer-authenticated Unix IPC **clients** for independently operated witness and durable permit-ledger contracts, strict four-UID OS boundary preflight, executable recovery service runtime, three uninstalled systemd unit *examples*, two test modules with real cross-UID fault injection. No independent production provider, no systemd activation, no evidence of complete legacy fencing. Software release `BLOCKED` and physical rail operations `NO-GO`. See `docs/RAIL-TRUST-012.md`.

## v0.23 — RAIL-TRUST-013
Experimental dedicated production **software release write authority** under a
service UID, kernel-authenticated client IPC, strict operator-owned state and
rejection of legacy IPC verbs. Configuration: `systemd/railsystem-write.service.example`.
Rootless/independent production CAS and durable permit services are NOT provided;
the supplied test doubles are intentionally volatile. Host root or arbitrary
same-service-UID code can bypass these library-level controls. Production
`BLOCKED`; physical operation `NO-GO`. Details: `docs/RAIL-TRUST-013.md`.

## v0.24 — RAIL-TRUST-014
Laboratory-only UID-separated SQLite-backed witness and permit authorities, actual
Linux `SO_PEERCRED` IPC integration, SIGKILL before/after local COMMIT regression,
and conservative *production CLI fail-closed* policy when independently verified
MAC isolation / anti-rollback trust roots are missing. These local authorities
are **not production-ready** and are rollbackable with their host filesystem.
Systemd examples are not activated. See `docs/RAIL-TRUST-014.md` and
`deployment/RAIL-TRUST-014_os_requirements.json`. Status PARTIAL/BLOCKED/NO-GO.

### RailSystem v0.25 / RAIL-TRUST-015

Adds `monotonic_root.py` Ed25519 pinned-challenge quote verification (protocol-only;
**no independent root is supplied**), richer `os_managed_fencing` MAC/manager
probe, and a mandatory pre-admission OS gate for production `release_cli`
(`trust_cli` aliases it). `write_authority` and `service_runtime` remain gated.
The full archive retains all earlier library APIs and tests. Current environment
cannot attest same-UID LSM confinement, independent monotonic storage or
supervised end-to-end recovery. **PARTIAL / BLOCKED / NO-GO**. See
`docs/RAIL-TRUST-015.md` and `deployment/RAIL-TRUST-015_independent_requirements.json`.
