# LOG-CORE-017 architecture
Opt-in QuarantinedTransactionService extends ConsistencyGatedLogisticsService and AttestedLogisticsService.
TransactionSnapshot exposes COMMITTED, QUARANTINED_PHASE, QUARANTINED_DIVERGENCE.
The service compares current ledger head, local checkpoint and independent witness; a pending journal is quarantined rather than reconciled.
The phase reader uses O_NOFOLLOW, fstat, link count, owner and mode checks, and bounded reads.
No production entry point is enabled. Existing library entry points are intentionally retained for compatibility, so OS-enforced legacy fencing is not established.
No authenticated distributed transaction protocol, independent witness durability attestation or full four-UID service orchestration is implemented here.
