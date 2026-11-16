# SnowPiercer Ecosystem Work Register — v20

Snapshot date: 2026-10-28

## Measurement policy
- Overall completion is **not calculated** until a weighted, approved deliverable baseline and evidence audit exist.
- Stage count is not a fixed percentage of ecosystem completion.
- Software tests do not establish physical-system readiness.
- Payment integration remains **NO-GO / NOT VERIFIED** until an external provider sandbox is independently tested and accepted.

## Current release
- TrainOS v61; stages 518–527.
- Focus: deterministic regression selection, audit edge cases, inventory evidence contract, full-suite and CI readiness.
- Targeted stages 518–527: 10 passed in 0.31s. Unified regression stages 170–527: 388 passed across 358 test files. Supporting tests (`tests/ci` and `tests/ledger_contract`): 70 passed. Pytest collected 1,346 tests. Python AST audit: 3,021 files, 0 syntax errors.
- A monolithic full-project pytest run was incomplete/timed out in the stage156 context; stage156 passed independently (3 passed in 3.48s). CI is configured to isolate stage directories with per-stage timeouts. GitHub Actions execution remains unverified until a hosted run is observed.

## Regression policy
- Use `scripts/ci/run_regression.py --start N --end M --report PATH`.
- Selection includes sorted unique `test_*.py` files recursively under `tests/stageN` for the inclusive range.
- The JSON report records exact selected files, command, exit code, elapsed time, and PASS/FAIL.
- Never compare regression counts from different selection rules as if they were the same metric.

## Ecosystem inventory
The detailed machine-readable deliverable baseline is `SNOWPIERCER/ECOSYSTEM_DELIVERABLE_BASELINE_V1.json`. It inventories nine modules: SP-SW, SP-AI, SP-RAIL, SP-ENERGY, SP-LIFE, SP-LOG, SP-SAFE, SP-ISLAND, and SP-OPS. Each has deliverables, acceptance evidence, and critical gates.

| Module | Status | Next evidence required |
|---|---|---|
| SP-SW — TrainOS/software | ACTIVE_IMPLEMENTATION | Unified regression and full-suite evidence; hosted CI; payment sandbox; restore drill |
| SP-AI — autonomy | INVENTORY_PENDING | Approved requirements, evaluation protocol, fail-safe and operator override tests |
| SP-RAIL — trains/rail | ENGINEERING_EVIDENCE_PENDING | Qualified engineering design, hazard analysis, physical/simulation test reports |
| SP-ENERGY — energy | FEASIBILITY_BASELINE_PENDING | Quantified load profile, protection analysis, endurance and emergency-mode tests |
| SP-LIFE — life support | INVENTORY_PENDING | Air/water/resource balances, medical plan, long-duration validation |
| SP-LOG — logistics/drones | INVENTORY_PENDING | Simulated end-to-end workflows, geofence/collision and reconciliation tests |
| SP-SAFE — safety/security | SAFETY_BASELINE_PENDING | Threat model, hazard analysis, security tests and independent review |
| SP-ISLAND — industrial island | SCOPE_DECOMPOSITION_PENDING | Site feasibility, permitting, engineering concept, cost baseline |
| SP-OPS — operations | INVENTORY_PENDING | Approved SOPs, training/drills, maintenance and change governance |

## Current limitations and blockers
- Weighted scope baseline is not approved; overall completion remains `null`.
- Monolithic full-suite result is INCOMPLETE_TIMEOUT; CI uses per-stage isolation. Hosted CI remains NOT_RUN.
- GitHub Actions configuration is updated locally but no hosted run is claimed.
- External payment sandbox, backup authenticity, off-host durability, distributed exactly-once execution, and RPO/RTO are not proven.
- Physical subsystems require independent engineering and safety evidence.

## Release verification
See `TrainOS_Financial_Ledger_Contract_v61_manifest.json` for actual test outcomes, full-suite timeout details, AST audit, ZIP integrity, cache exclusion, and SHA-256.
