# SP-OPS v0.1.0 — Integration & Operations architecture

**Baseline:** `TrainOS_Workspace(5).zip` (ECO-001); date: 2026-11-15. This is not an update to later releases already developed in other chats. **Decision: NO-GO.**

## Mission, scope, authority

SP-OPS is the ninth governance/integration subsystem, complementary to TrainOS. It owns traceability, interface lifecycle, integrated verification plans, evidence inventory, incident and configuration management, change-control documentation and post-validation operational acceptance planning. It **does not** operate railway equipment, energize systems, issue safety permits or override any module's safety gate.

| Component | Responsibility | Current implementation |
|---|---|---|
| Inventory | Baselines of the nine modules, dependencies and artifact SHA-256 | `config/catalog.json`; `ops_core.py` |
| Evidence ingestion | Read-only inventory of file existence, metadata and matching hashes | `artifact_observation` (local only) |
| Readiness assessment | Explicit blockers, cycles, missing or divergent artifacts, no computed completion % | `assess`, hard NO-GO |
| Interface authority | Versioned contract proposals, unit semantics and denial defaults | `contracts/interfaces.json` (proposal only) |
| Validation | Reproducible negative/positive unit tests for the assessment tool | `tests/test_ops_core.py` |
| Operations | Change records, incident response, drills, handover and independent review | `docs/OPERATIONS_PLAN.md` (planning only) |

The previous six `integration/probes.py` are retained untouched and continue to verify independent local API boundaries, **not** connected module-to-module interfaces. Neither their historical PASS nor this scanner's hash matches are independent root-of-trust attestations.

## Trust and data flow

`workspace snapshot → baseline catalog → safe read-only artifact scan → SHA-256 comparison → dependency analysis → blocker matrix → assessment.json (NO-GO)`.

The catalog is not a trusted authority: an attacker able to alter both catalog and evidence can forge digest concordance. A future production-grade pipeline requires separately administered, monotonic, rollback-protected witness storage, signed provenance, independent review, hostile cross-UID/MAC enforcement, deployed binaries vs measured hash equivalence, safety evidence and physical commissioning. None is claimed here.

The scanner never imports or executes untrusted module code. Inputs are plain JSON and file paths. Paths with `..`, absolute paths, backslash, NUL, symlink components and directories are rejected. Missing/unsafe evidence is a finding. Race-free no-follow openat2 / O_NOFOLLOW per component, cryptographically authentic configuration and an independent service manager are **not** implemented: run only against a controlled, immutable snapshot for meaningful checks.

Existing registry lists mutual readiness dependencies `SP-SAFE ↔ SP-OPS`, a circularity to resolve by defining separate *review* relationships and independent trust authority. The scanner reports cycles instead of silently treating them as satisfied.

## Boundary decisions

- `NO_GO`: sole possible operational decision in this release. Assessment is advisory and cannot grant rights.
- `PENDING`: baseline lacks evidence; `SOFTWARE_OBSERVED_NO_GO` or `ARCHIVED_NO_GO`: source provenance only, not readiness.
- `DIGEST_MATCH_UNATTESTED`: on-disk bytes match the expected digest published in the same workspace. This is **not** integrity against a workspace attacker.
- `PRESENT_UNATTESTED`: a local file exists without a separate expected digest.
- `DIGEST_MISMATCH` / `UNAVAILABLE_OR_UNSAFE`: fail the artifact integrity check.

Blocking conditions include missing evidence, dependency cycles, Security baseline pending, missing cross-UID/MAC root, physical HIL, integrated hazard closure and formal operational acceptance.

## Version and compatibility

- Own version: **SP-OPS v0.1.0**, initial foundation release; no additional numbered Stage created.
- Other module source versions and TrainOS v101 are **unchanged**. No changes to their APIs, admission or safety mechanisms.
- Existing `integration/` runner, schemas, workspace site and historical evidence preserved.
- The tool's JSON schema is `snowpiercer.ops-assessment.v1`; changes require versioned migration.
