# ISLAND-GEO-015 — state-bound recovery and evidence boundaries

New `BoundPermitAuthority` adds UID and exact witness head binding to one-use recovery tokens. Existing APIs remain unchanged. `assert_legacy_fenced` checks ownership and directory modes but is NOT a complete OS-enforced deployment proof.

## Critical gaps

The new permit authority is not wired into the inherited `AuthorizedProductionServer` and `AuthorityServer`; the inherited production path still uses the Stage 014 permit scheme. A privileged operator, compromised witness UID, or rollback of both witness and permit databases can defeat these controls. Direct client attestation is not implemented. Production IPC SIGKILL coverage is incomplete.

## Threat model

Adversary controls an unprivileged client and can attempt replay, stale token use, and direct filesystem access. Root and witness UID compromise are out of scope; independent hardware monotonicity is not present. A local file permission check is only preflight, not proof of an enforced privilege boundary.

## Deployment status

Independent production security: BLOCKED/NO-GO. Physical construction and operations: BLOCKED/NO-GO.
