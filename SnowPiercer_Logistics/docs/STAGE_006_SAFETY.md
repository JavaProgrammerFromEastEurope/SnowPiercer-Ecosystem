# Stage 006 safety analysis
- Local marker replay: blocked for the same filesystem state; deleting marker allows replay.
- Rollback of entire filesystem including marker: not prevented.
- Witness rollback: witness file is not hardware-backed or otherwise immutable.
- File swap / TOCTOU: path checks do not fully prevent hostile concurrent modification.
- SIGKILL: durable marker and atomic checkpoint operations are used, but exhaustive crash-point verification has not been performed.
- Distinct UID isolation: not demonstrated by tests; local tests run under one UID.
- Production bypass: legacy LogisticsLedger remains callable; OS-enforced fencing not implemented.
- Fail closed on mismatch: tested only for selected scenarios.
- Decision: BLOCKED/NO-GO.
