# ISLAND-GEO-011 Architecture and limits

- Retain all prior library APIs; `deployment_gate` is additive.
- Three distinct non-root UIDs: client, admission service, witness.
- Production DB and phase journal must be writable only by service; witness DB only by witness.
- Peer identity must be verified on connected sockets using SO_PEERCRED.
- A static mode check is NOT proof of OS-enforced legacy fencing.
- A local SQLite witness does NOT prevent witness-owner rollback.
- The inherited service is still opt-in; mandatory production entrypoint is NOT established.
- Crash-point exhaustiveness is NOT established.
- On any unverified condition: BLOCKED/NO-GO.
