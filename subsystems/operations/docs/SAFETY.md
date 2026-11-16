# SP-OPS risk and assurance register (initial)

| Hazard | Example initiating condition | Required independent control | Present evidence / decision |
|---|---|---|---|
| OPS-H-01 | Energy outage propagates into rail braking/life support | Independent safe-state design; real HIL failover | Missing / NO-GO |
| OPS-H-02 | Stale telemetry accepted as current | Typed SI, quality/freshness enforcement at receivers, E2E timing | Local module probes only / NO-GO |
| OPS-H-03 | AI suggestion becomes equipment command | Hard privileges, human/safety approval, no shared actuation authority | Proposal interface only / NO-GO |
| OPS-H-04 | Rollback enables replay of permit | Independent protected monotonic root and durable spend witness | Not demonstrated / NO-GO |
| OPS-H-05 | Same-UID legacy path bypasses admission | OS-enforced MAC/LSM confinement, verified deployment controls | Not demonstrated / NO-GO |
| OPS-H-06 | SIGKILL/restart races create dual owners | Service-manager authority, durable reconciliation, cross-UID fault injection | Not demonstrated E2E / NO-GO |
| OPS-H-07 | Geotechnical failure exceeds design basis | Geotechnical safety case, sensor/analysis validation, permit review | Physical assessment missing / NO-GO |
| OPS-H-08 | Evidence spoofing or tampered build | Signed immutable provenance outside local workspace, secure boot/deploy | Local hash check insufficient / NO-GO |
| OPS-H-09 | Operator emergency action not effective | Independently proven emergency stop, exercised procedures and failover | Not commissioned / NO-GO |
| OPS-H-10 | Dependency acceptance is circular | Explicit authority split; directed dependency graph reviewed | SP-SAFE/SP-OPS cycle detected / NO-GO |

**Assurance boundary:** A standalone development environment cannot provide proof about physical plant safety, verified OS MAC policy, independent hardware roots or certified operational procedures. The operating gate remains NO-GO. Any future GO mechanism requires a new architecture and independent authorities, not removal of assertions in this scanner.
