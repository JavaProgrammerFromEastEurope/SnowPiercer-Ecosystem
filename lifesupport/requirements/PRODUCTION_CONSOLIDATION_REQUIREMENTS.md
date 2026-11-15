# LIFE-CORE-020 requirements

- LIFE-020-R01: Production mode requires explicit opt-in provisioning.
- LIFE-020-R02: Production profile is stored in service-owned private DB directory.
- LIFE-020-R03: Production profile is a regular file with mode 0600.
- LIFE-020-R04: Profile path must not be a symbolic link.
- LIFE-020-R05: Legacy production CLI refuses launch when profile is present.
- LIFE-020-R06: Production supervisor selects mandatory ledger IPC.
- LIFE-020-R07: Missing or invalid production profile fails closed for production supervisor.
- LIFE-020-R08: Legacy library APIs remain available for non-production use.
- LIFE-020-R09: Profile creation must not overwrite an existing profile.
- LIFE-020-R10: Evidence must distinguish CLI admission from OS isolation.
- LIFE-020-R11: All existing tests must be re-run with ResourceWarning escalated.
- LIFE-020-R12: Fault tests from prior Stages remain part of cumulative regression.
