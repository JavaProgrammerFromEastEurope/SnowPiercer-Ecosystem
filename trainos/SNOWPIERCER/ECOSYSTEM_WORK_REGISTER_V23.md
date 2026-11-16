# SnowPiercer Ecosystem Work Register — v23

Snapshot date: 2026-10-28

## Current release
- TrainOS v64; stages 548–557.
- Focus: per-stage diagnostic reports, deterministic ranking of slow stages, status/exit-code validation, missing-stage detection, and CI diagnostic artifacts.
- Targeted stages 548–557: **10 passed**. Unified regression stages 170–557: **418 passed across 388 test files**. Supporting checks (`tests/ci`, `tests/ledger_contract`): **70 passed**. Collection: **1,376 tests**.
- Full-suite status is **INCOMPLETE_TIMEOUT**. Verbose output reached the stage137 multiprocessing retry-race test at the 30-second limit. That test passed in isolation (2.64 s) and stages 100–137 passed as a group (95 tests, 20.96 s); cause of the full-suite order-sensitive slowdown is not confirmed.

## Measurement policy
- Overall ecosystem completion remains **not calculated** until scope, weights, acceptance criteria, dependencies, and evidence are approved.
- Stage count is not an ecosystem completion metric. Software tests do not prove physical-system readiness.
- Payment integration remains **NO-GO / NOT VERIFIED** until the external provider sandbox is independently tested and accepted.

## Regression and CI policy
- Use `python scripts/ci/run_regression.py --start N --end M --timeout-seconds 1800 --report PATH`.
- Selection includes sorted unique `test_*.py` files recursively under `tests/stageN` for the inclusive range. Explicit includes must resolve under `tests/` and match `test_*.py`.
- Use `python scripts/ci/diagnose_stage_matrix.py SUMMARY.tsv --check-logs --expect-start N --expect-end M --require-complete --json diagnostics.json` to validate outcomes, identify missing stages, and rank slow stages.
- `PASS`, `FAIL`, and `TIMEOUT` remain distinct. A timeout never counts as a pass. Diagnostic JSON is written atomically.
- CI matrix covers stages 1–557 without gaps or overlaps. Hosted GitHub Actions remains unverified until an actual workflow run is observed.

## Inventory baseline
The detailed inventory is `SNOWPIERCER/ECOSYSTEM_DELIVERABLE_BASELINE_V4.json`. It covers nine modules: SP-SW, SP-AI, SP-RAIL, SP-ENERGY, SP-LIFE, SP-LOG, SP-SAFE, SP-ISLAND, and SP-OPS. It records deliverables, dependencies, acceptance evidence, and explicit unknown statuses.

| Module | Status | Required next evidence |
|---|---|---|
| SP-SW — TrainOS/software | ACTIVE_IMPLEMENTATION | Resolve full-suite order-sensitive slowdown, finish full suite, hosted CI, payment sandbox and off-host restore drill |
| SP-AI — autonomy | INVENTORY_PENDING | Approved requirements, evaluation protocol, fail-safe and operator override tests |
| SP-RAIL — trains/rail | ENGINEERING_EVIDENCE_PENDING | Qualified engineering design, hazard analysis and physical/simulation test reports |
| SP-ENERGY — energy | FEASIBILITY_BASELINE_PENDING | Quantified load profile, protection analysis, endurance and emergency-mode tests |
| SP-LIFE — life support | INVENTORY_PENDING | Air/water/resource balances, medical plan and long-duration validation |
| SP-LOG — logistics/drones | INVENTORY_PENDING | Simulated end-to-end workflows, geofence/collision and reconciliation tests |
| SP-SAFE — safety/security | SAFETY_BASELINE_PENDING | Threat model, hazard analysis, security tests and independent review |
| SP-ISLAND — industrial island | SCOPE_DECOMPOSITION_PENDING | Site feasibility, permitting, engineering concept and cost baseline |
| SP-OPS — operations | INVENTORY_PENDING | Approved SOPs, training/drills, maintenance and change governance |

## Known limitations
- Full pytest suite remains incomplete; no total pass/fail count is claimed.
- Hosted GitHub Actions has not been observed.
- External payment sandbox, backup authenticity, off-host durability, distributed exactly-once execution, and RPO/RTO remain unproven.
- Physical modules require independent engineering and safety evidence.

## Release evidence
See `TrainOS_Financial_Ledger_Contract_v64_manifest.json` and `docs/release_evidence/v64/` for target tests, regression report, stage diagnostics, collection summary, full-suite timeout details, AST audit, and limitations.
