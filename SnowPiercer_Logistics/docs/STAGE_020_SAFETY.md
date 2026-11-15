# Safety analysis / explicit limitations

Confirmed: local kernel file type/ownership checks, deterministic classification, strict regression compatibility, fail-closed opt-in entrypoint.
Not confirmed: four independent UIDs executing the *actual* ledger-witness-authority-recovery transaction; OS enforcement across every legacy production path; credential forwarding resistant to service compromise; rollback resistance to genesis; SQLite/witness CAS atomicity; independent permit DB rollback protection; socket and parent path TOCTOU; real SIGKILL at all transaction boundaries; production readiness.
The process owner/root can bypass DAC and filesystem rollback can defeat local checks. No independent end-to-end certification exists. Decision BLOCKED / NO-GO.
