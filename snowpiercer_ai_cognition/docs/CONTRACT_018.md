# AI-CORE-018 contract

`CrashInjector(point, enabled=True)` permits only the enumerated points; otherwise raises. `inject_admission(journaled, envelope, injector)` requires a JournaledAdmissionGateway, and is test-only in a single isolated child process. It kills the current process with SIGKILL at the requested boundary. Never expose this function over IPC or enable in a live production worker.

`cold_recover` now handles PREPARED with checkpoint already equal to the verified current audit head, using the same signed permit validation and durable burn path. PREPARED with a checkpoint not equal to the old or verified new head is refused. No automatic recovery.

Ordinary admission rejection cleans the PREPARED intent only if `gateway.verify()` confirms the exact old trusted head; ambiguous outcomes retain fail-closed behavior.
