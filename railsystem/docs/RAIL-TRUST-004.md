# RAIL-TRUST-004 — Independent Trust Anchor & Production Recovery Fencing

Status: PARTIAL / SOFTWARE PROTOTYPE / PRODUCTION NO-GO.

## Requirements and contracts
- RAIL-TRUST-004-R01: production release CLI shall fail closed without independent trusted anchor provider.
- RAIL-TRUST-004-R02: provider interface shall expose read and atomic monotonic compare-and-swap advance; its actual trustworthiness must be independently verified.
- RAIL-TRUST-004-R03: admission preflight shall reject non-IDLE phases and disagreement between SQLite, local anchor and external anchor.
- RAIL-TRUST-004-R04: offline recovery requires an Ed25519-signed, domain-separated, sequence-scoped permit.
- RAIL-TRUST-004-R05: consumed permits shall be stored in SQLite atomically with local recovery transition.
- RAIL-TRUST-004-R06: preserve library API compatibility and prohibit legacy unsigned production CLI options.

## Safety analysis
The supplied IndependentAnchor is an intentionally unimplemented interface. No hardware security module, remote monotonic counter, trusted service or authenticated transport is provided. Production CLI is therefore BLOCKED. The test-only in-memory provider does not establish security.

A preflight independent-anchor read followed by the prior Stage admission is not a unified atomic transaction. A provider-backed release could race a concurrent state change; therefore an externally provisioned provider MUST NOT be interpreted as a production-ready implementation. Atomic provider advancement is not integrated with the SQLite/local-anchor phase journal. No end-to-end durability guarantee exists.

Recovery permits are authenticated using a caller-provided public key. Binding this key to an independently administered recovery authority is outside this Stage. SQLite permit history can be rolled back together with SQLite. Cross-UID access is intentionally denied by owner-controlled directory checks; no privilege-separated recovery broker exists. No IPC socket is introduced, so socket substitution resistance is untested.

Existing library APIs remain callable, including older legacy evaluate/admit functions. They are NOT production authorization APIs, but eliminating all potential embedding bypasses is unproven.

## Evidence and missing tests
Nine added local unit tests cover default denial, consistency, disagreement, phase fence, signature tampering, scope, permit replay, unavailable provider and symlink path. Three complete unittest runs use warning filters as errors. SIGKILL at every commit boundary, UID-separated recovery, concurrent startup, hostile filesystem mutation and socket substitution have NOT been demonstrated. External monotonicity, power-loss durability and physically independent rollback resistance remain unverified.

## Acceptance
Software unit-test gate: PASS. Independent provider integration: BLOCKED. Production software admission: BLOCKED. Rail safety and physical operation: NO-GO.
