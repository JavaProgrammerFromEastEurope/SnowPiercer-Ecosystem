# SnowPiercer Ecosystem Work Register — v22

Snapshot date: 2026-10-28

## Current release
- TrainOS v63; stages 538–547.
- Focus: regression include-path safety, atomic JSON evidence reports, CI range consistency, and inventory baseline contracts.
- Targeted stages 538–547: **10 passed**. Unified regression stages 170–547: **408 passed across 378 test files**. Supporting checks (`tests/ci`, `tests/ledger_contract`): **70 passed**. Collection: **1,366 tests**.
- Full-suite attempts were interrupted by tool timeouts at 180 and 300 seconds. Full-suite status is **INCOMPLETE_TIMEOUT**, not PASS. See `docs/release_evidence/v63/`.

## Measurement policy
- Overall ecosystem completion is **not calculated** until scope, weights, acceptance criteria, dependencies, and evidence are approved.
- Stage count is not an ecosystem completion metric.
- Software tests do not prove physical-system readiness.
- Payment integration remains **NO-GO / NOT VERIFIED** until the external provider sandbox is independently tested and accepted.

## Regression and CI policy
- Use `python scripts/ci/run_regression.py --start N --end M --timeout-seconds 1800 --report PATH`.
- Selection includes sorted unique `test_*.py` files recursively under `tests/stageN` for the inclusive range.
- Explicit include paths must resolve inside `tests/` and use the `test_*.py` naming convention.
- Execution reports are written atomically. A timeout is recorded as `TIMEOUT` with exit code 124 and machine-readable evidence.
- CI stage matrix covers stages 1–547 without gaps or overlaps. The stage runner and summary tool have executable permissions.
- Hosted CI remains unverified until an actual GitHub Actions run is observed.

## Inventory baseline
The detailed inventory is `SNOWPIERCER/ECOSYSTEM_DELIVERABLE_BASELINE_V3.json`. It covers nine modules: SP-SW, SP-AI, SP-RAIL, SP-ENERGY, SP-LIFE, SP-LOG, SP-SAFE, SP-ISLAND, and SP-OPS. It records deliverables, dependencies, acceptance evidence, and explicit unknown statuses.

| Module | Status | Required next evidence |
|---|---|---|
| SP-SW — TrainOS/software | ACTIVE_IMPLEMENTATION | Full suite completion, hosted CI, payment sandbox and off-host restore drill |
| SP-AI — autonomy | INVENTORY_PENDING | Approved requirements, evaluation protocol, fail-safe and operator override tests |
| SP-RAIL — trains/rail | ENGINEERING_EVIDENCE_PENDING | Qualified engineering design, hazard analysis and physical/simulation test reports |
| SP-ENERGY — energy | FEASIBILITY_BASELINE_PENDING | Quantified load profile, protection analysis, endurance and emergency-mode tests |
| SP-LIFE — life support | INVENTORY_PENDING | Air/water/resource balances, medical plan and long-duration validation |
| SP-LOG — logistics/drones | INVENTORY_PENDING | Simulated end-to-end workflows, geofence/collision and reconciliation tests |
| SP-SAFE — safety/security | SAFETY_BASELINE_PENDING | Threat model, hazard analysis, security tests and independent review |
| SP-ISLAND — industrial island | SCOPE_DECOMPOSITION_PENDING | Site feasibility, permitting, engineering concept and cost baseline |
| SP-OPS — operations | INVENTORY_PENDING | Approved SOPs, training/drills, maintenance and change governance |

## Known limitations
- Full pytest suite is incomplete due to tool timeout; no final full-suite count is claimed.
- GitHub Actions hosted execution has not been observed.
- External payment sandbox, backup authenticity, off-host durability, distributed exactly-once execution, and RPO/RTO remain unproven.
- Physical modules require independent engineering and safety evidence.

## Release evidence
See `TrainOS_Financial_Ledger_Contract_v63_manifest.json` and `docs/release_evidence/v63/` for actual test results, selected file lists, AST audit, and limitations.
