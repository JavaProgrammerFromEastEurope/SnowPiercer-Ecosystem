# LIFE-CORE-004 — preliminary hazard review

| Hazard | Mitigation | Residual limitation |
|---|---|---|
| Torn or malformed journal entry | SQLite transactions, strict replay validation | Storage/controller defects not tested |
| Corrupt or forged event | SHA-256 event-chain validation | No trusted signature or external anchor |
| Missing internal event | Strict contiguous sequence and chain | Tail truncation without external anchor undetectable |
| Conflicting writers | BEGIN IMMEDIATE and replay inside transaction | Distributed coordination not supported |
| Configuration drift | Registry fingerprint | Fingerprint not authenticated |
| Lost physical equipment state | No physical control or actuation | Logical state must not be treated as real equipment state |
| Backup inconsistency | Document SQLite online backup requirements | Backup/restore not yet automated |

**Safety decision:** NO-GO for physical deployment and safety-critical operation.
