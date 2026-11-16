# TrainOS v70 — physical functional stage migration

Moved 10 diagnostic modules from numbered stage578–587 directories into
`tests/domains/pytest_diagnostics/`, with import-root fixes and pinned ownership
registry cleanup. See AUDIT/FUNCTIONAL_STAGE_PHYSICAL_MIGRATION_V70.json.

This is an incremental migration, not a wholesale move of all legacy tests.
Full suite and hosted CI: NOT_RUN.
