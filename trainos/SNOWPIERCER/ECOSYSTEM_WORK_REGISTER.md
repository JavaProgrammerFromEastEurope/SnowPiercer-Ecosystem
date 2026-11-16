# SnowPiercer Ecosystem Work Register — v25

Snapshot date: 2026-10-28

## Current release
- TrainOS v66; stages 568–577.
- Focus: robust pytest progress parsing, collection count extraction, bounded diagnostics, and CI matrix coverage through stage 577.
- Targeted stages 568–577: **10 passed**. Unified regression stages 170–577: **439 passed across 408 test files**. Supporting checks (`tests/ci`, `tests/ledger_contract`): **70 passed**. Collection: **1,397 tests**.
- Full-suite status is **INCOMPLETE_TIMEOUT**. The outer execution environment interrupted the local run after progress into stage178. The preserved log contains 359 completed PASS outcomes and zero observed failures, but no final pytest exit status; no full-suite pass is claimed.

## Measurement policy
- Overall ecosystem completion remains **not calculated** until scope, weights, acceptance criteria, dependencies, and evidence are approved.
- Stage count is not an ecosystem completion metric. Software tests do not prove physical-system readiness.
- Payment integration remains **NO-GO / NOT VERIFIED** until the external provider sandbox is independently tested and accepted.

## Regression and CI policy
- Run `python scripts/ci/run_regression.py --start N --end M --timeout-seconds 1800 --report PATH` for the inclusive stage range.
- Run `python scripts/ci/run_pytest_diagnostic.py --root . --timeout-seconds 600 --tail-lines 40 --log test-logs/full-suite-verbose.log --report test-logs/full-suite-diagnostic.json` for full-suite progress and timeout evidence.
- The diagnostic records collection count, last observed/completed tests, outcome counts, elapsed time, timeout budget, and a bounded log tail. It supports pytest import-mode output that inserts a `<- source/path.py` annotation before the outcome. JSON is written atomically.
- `PASS`, `FAIL`, and `INCOMPLETE_TIMEOUT` remain distinct. An interrupted run without a final child exit status is incomplete, not a pass or an assertion failure.
- CI matrix covers stages 1–577 without gaps or overlaps. Hosted GitHub Actions remains unverified until an actual workflow run is observed.

## Inventory baseline
The detailed inventory is `SNOWPIERCER/ECOSYSTEM_DELIVERABLE_BASELINE_V6.json`. It covers nine modules: SP-SW, SP-AI, SP-RAIL, SP-ENERGY, SP-LIFE, SP-LOG, SP-SAFE, SP-ISLAND, and SP-OPS. It records deliverables, dependencies, acceptance evidence, and explicit unknown statuses.

| Module | Status | Required next evidence |
|---|---|---|
| SP-SW — TrainOS/software | ACTIVE_IMPLEMENTATION | Complete full suite, inspect timing across whole suite, hosted CI, payment sandbox and off-host restore drill |
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
See `TrainOS_Financial_Ledger_Contract_v66_manifest.json` and `docs/release_evidence/v66/` for targeted tests, regression report, stage diagnostics, collection summary, full-suite interruption evidence, AST audit, workflow validation, and limitations.
