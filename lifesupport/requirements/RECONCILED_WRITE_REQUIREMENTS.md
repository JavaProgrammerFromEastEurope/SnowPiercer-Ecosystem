# LIFE-CORE-017 requirements

- R017-01: Production IPC shall require a distinct authorized client UID.
- R017-02: The write service shall run under a non-root dedicated UID.
- R017-03: A transition request shall include a bounded nonempty request_id.
- R017-04: The service shall bind a request_id to the authenticated peer UID and canonical request payload.
- R017-05: The event and receipt shall commit atomically in SQLite.
- R017-06: An identical retry shall return the durable receipt without a new event.
- R017-07: A conflicting request_id shall fail closed.
- R017-08: An authorized peer shall query only its own receipt.
- R017-09: A supervised child shall be restarted following SIGKILL.
- R017-10: Connected peer PID and UID shall be verified during readiness.
- R017-11: A stale socket shall be reconciled without deleting foreign or live sockets.
- R017-12: Fault injection shall test both sides of COMMIT.
- R017-13: Legacy Stage-016 production IPC shall remain opt-in and compatible.
- R017-14: SQLite ResourceWarnings shall be treated as errors during regression.
- R017-15: No physical life-support actuation shall be exposed.
