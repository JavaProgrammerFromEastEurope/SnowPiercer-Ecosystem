# RAIL-CI-001 — Continuous Integration & Release Gates

A fail-closed software-only release gate with PASS, FAIL, BLOCKED. The gate validates test inventory, full unittest regression, and source integrity against an externally approved SHA-256 manifest. Without an approved baseline, the release remains BLOCKED. A self-generated manifest must not be treated as independent approval. CI runs regression and verifies BLOCKED status until a controlled baseline workflow is introduced. GitHub Actions execution has not been verified remotely.

Run: `python -m railsystem.release_cli --output ../release-gate.json` (exit 2 for BLOCKED).

Safety: no actuation, physical integration, operational authorization, certification or independent review.
