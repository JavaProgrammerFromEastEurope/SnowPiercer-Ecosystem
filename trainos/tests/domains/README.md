# Functional TrainOS stages

A Stage is a **functional test domain**, not a chronological release number.
New tests go under `tests/domains/<domain>/test_*.py` and are automatically included in the existing domain by `tests.kernel_runner.config.discover_stages()`.
Legacy numbered test paths remain unchanged for backward compatibility. Their ownership is pinned in `tests/kernel_runner/legacy_domain_assignments.json`; new numbered legacy tests are rejected until explicitly assigned.
The initial v67 ownership mapping is provisional, especially `legacy_contracts`; do not interpret keyword classification as verified semantic ownership.
Run `python -m pytest -q tests/domains/ci_release tests/domains/pytest_diagnostics` for migration contracts.

## v70 physical migration
Ten pytest diagnostic contract modules (formerly numbered 578–587) now reside in
`tests/domains/pytest_diagnostics/`. Their project-root discovery was updated for
the deeper directory. `AUDIT/FUNCTIONAL_STAGE_PHYSICAL_MIGRATION_V70.json`
records exact old-to-new paths. The legacy ownership registry contains only
modules still in numbered directories. Historical path-based commands for these
ten modules must use their new paths; this is an intentional breaking change
for those explicit file references.
