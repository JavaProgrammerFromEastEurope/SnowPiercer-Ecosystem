# ISLAND-GEO-007 — Evidence-to-Measurement Binding & Independent Source Trust

## Scope
Canonical JSON with no floats, exact decimal strings, strict units, UTC timestamps and an explicitly supplied scenario epoch. Ed25519 source signatures use a domain separator; source public keys are authorized by a separately root-signed policy. Local SQLite BEGIN IMMEDIATE protects concurrent replay admission and monotonically increasing source sequence and policy versions **only while the ledger persists**.

## Trust boundaries
Root key is injected, not hardware pinned; a caller that replaces both root and policy can forge trust. The epoch is caller-provided and must be independently authenticated. No instrument attestation or external immutable witness exists. Signed source data may be untrue; numeric agreement does not establish geotechnical accuracy. The ledger can be deleted, restored from an old backup, or tampered with by its OS owner. A valid source can equivocate before first admission. This is NOT an independently secured production trust boundary.

## Conservative behavior
Missing/modified data, invalid signatures, mismatched units, missing epoch agreement, or replay deny admission with risk escalation and no numerical outputs. No production physical control is enabled. Physical deployment is BLOCKED/NO-GO.

## Model limitations
Exact Decimal(str(float)) equality reflects existing float-backed models, not lossless measured decimals. Signature trust is policy-scoped, not a certificate authority. Scenario temporal values are relative days mapped to whole-second UTC times; subsecond collisions are not resolved and must be excluded by deployment policy. Rollback-resistant admission requires an independently administered external monotonic witness and OS-enforced key/ledger isolation.
