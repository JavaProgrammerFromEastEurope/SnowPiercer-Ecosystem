# RAIL-EVID-001 — Evidence Provenance & Release Baselines

## Scope
Offline candidate SHA-256 baseline, canonical manifest digest, structural integrity validation, inventory comparison, regression evidence checks, and conservative release decision.

## Trust boundary
A candidate baseline is **not approved**. Approval must be verified using independent trust anchors and authenticated signatures; neither exists in this Stage. An `approved: true` JSON field never grants approval. Therefore the release gate remains BLOCKED (or FAIL on inconsistency), never PASS. SHA-256 alone does not prove provenance.

## Acceptance
Automated negative tests cover invalid IDs, tampered manifests, path traversal, missing evidence, fake approval, mismatched inventory, and invalid regression results. Independent safety assessment and physical operations are out of scope.
