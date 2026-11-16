# Threat model and preliminary hazard register (not accepted)

| ID | Failure/attacker capability | Safety impact | Required mitigation | Evidence status |
|---|---|---|---|---|
| T-01 | Replay of the same authorized operation | Duplicate physical effect | Persisted nonce + transaction + idempotent device command | Local simulation only |
| T-02 | Rollback to genesis or earlier SQLite image | Revives spent permit / historical policy | Independent monotonic witness, separate UID and root of trust | NO-GO |
| T-03 | Same-UID legacy production bypass | Skips policy admission | MAC/LSM enforce legacy confinement and complete entrypoint audit | NO-GO |
| T-04 | Fake broker, socket replacement or forged peer identity | Unauthenticated actuation | OS peer credentials, label checks, safe socket creation, strict path ownership | NO-GO |
| T-05 | SIGKILL between ledger write, witness CAS, permit consumption | Inconsistent durable state | Explicit crash protocol and fault injection at every boundary | NO-GO |
| T-06 | Compromised local HMAC key | Forged audit decisions | Hardware/isolate-held keys, lifecycle rotation, separate witness | NO-GO |
| T-07 | Manipulated AI proposal | Unsafe autonomy escalation | Independently enforce human approval and no direct proposal-to-actuation | NO-GO |
| T-08 | Attack on TrainOS scheduling/cgroup authority | Unconfined subprocess executes | Independent manager and OS enforced execution admission | NO-GO |
| T-09 | Failure of logging | Untraceable permission | Refuse any admission before a durable audit commit | Tested for local DB errors only |
| T-10 | Corrupt telemetry / safety controller compromise | Physical harm | Validated origin, freshness, quality, independent hardware trip | NO-GO |

Adversary assumptions in the **current tested implementation**: untrusted JSON
request and client-supplied simulated principal, SQLite corruption by file-level edits;
no hostile kernel, no hostile root, no cross-UID OS isolation. Root-level attackers,
attestation, independent keys and actual fault-injection lie outside the tested scope.
