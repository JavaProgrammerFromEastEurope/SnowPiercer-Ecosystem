# Financial Ledger Contract v10 — rollback-aware checkpoints

Date: 2026-10-24

## Scope

This additive stage extends v9 external HMAC-SHA256 checkpoints with a monotonic sequence field, an optional previous-manifest SHA-256 link, and verifier inputs for anti-rollback enforcement. Existing calls remain compatible: the default sequence is `1`, and anti-rollback checks are opt-in unless the caller supplies trusted state.

## New controls

- `create_checkpoint(..., sequence=N, previous_manifest_sha256=...)` signs a positive sequence and optional digest link to the prior manifest.
- The returned report includes `manifest_sha256`, allowing a caller to pin the exact checkpoint in a separately protected monotonic store.
- `verify_checkpoint(..., minimum_sequence=N)` rejects a signed but older checkpoint below a caller-supplied trusted floor.
- `verify_checkpoint(..., expected_manifest_sha256=...)` requires the exact manifest digest retained by a trusted external system.
- The manifest sequence and previous digest are covered by HMAC; malformed sequence values and malformed digest links are rejected.

## Critical trust boundary

Sequence values and hash links alone do **not** prevent rollback. An attacker could present an older correctly signed checkpoint unless the verifier obtains `minimum_sequence` and/or `expected_manifest_sha256` from storage that the attacker cannot roll back or rewrite. Suitable examples include a protected remote audit service, append-only transparency log, hardware-backed monotonic counter, or separately permissioned control plane. Do not store the only trusted latest digest next to the SQLite database and assume it is tamper-proof.

This feature does not automatically enforce contiguous sequence progression or verify the full previous-manifest chain. The caller that creates checkpoints must serialize checkpoint publication and update the trusted head atomically in the external control plane. If that control plane update fails, treat the new checkpoint as unpublished and reconcile before continuing.

## Tests

Added tests for valid sequence progression, previous-manifest linkage, minimum-sequence rejection, expected-digest rejection, and invalid sequence values. Full TrainOS suite is not run as part of this stage.

## Status

`experimental / isolated prototype`. Not approved for real-money transactions. Production approval still requires an independently protected monotonic trust anchor, external settlement reconciliation, authorization controls, retention policy, full CI, load testing, and independent security/accounting review.
