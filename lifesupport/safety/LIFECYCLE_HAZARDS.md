# LIFE-CORE-003 Preliminary Hazard Analysis

| Hazard | Risk | Mitigation / remaining gap |
|---|---|---|
| Mistaking logical ACTIVE for equipment readiness | Dangerous reliance on simulation | Documented as logical only; physical proof not implemented |
| Blocking protective isolation because a dependent remains ACTIVE | Potentially unsafe interlock | ACTIVE exit guard is simulation-only; physical safety system must override |
| Lost events on process restart | Incorrect state history | No durable store; persistence needed |
| Malicious modification of event chain | False evidence | Hash chain is not signed; trusted append-only store needed |
| Concurrent transition race | Inconsistent state | No concurrency support; single-thread scope |
| Incorrect system time | Misordered events | UTC validation only; secure time source needed |
| Untrusted external messages | Unauthorized state changes | No network receiver; authentication and authorization deferred |

Operational readiness: NO-GO. No field use permitted.
