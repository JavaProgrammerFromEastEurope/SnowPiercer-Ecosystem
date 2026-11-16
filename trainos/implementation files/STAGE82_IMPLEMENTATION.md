# Stage 82 — EventRegistry trusted-read integration

## Changes
- Added opt-in `anchor_store` and `require_trusted_reads` parameters to `EventRegistry`.
- In trusted-read mode, `get_events`, `all_events`, and `get_latest` re-assess the event log against the trusted anchor store before returning data.
- Configuration fails closed at construction when trusted reads are requested without both persistent stores.
- Default behavior remains backward compatible; deployments must explicitly enable trusted-read mode.

## Validation
- Focused tests for stages 78–82: **29 passed**.
- Full test suite: **618 passed**.
- `python -m compileall -q kernel tests`: passed.
- AST parse of all Python files under `kernel`: **2,132 files, 0 errors**.
- ZIP integrity check: passed after archive creation.

## Limitations
- This protects reads through `EventRegistry` only; direct `CommandEventStore` reads and other access paths are not intercepted.
- Anchor storage availability is required for every gated read; failures block the read rather than returning unverified history.
- Local SQLite storage is not independently immutable or remote. This is not a safety-certified train-control mechanism.
