# SP-OPS operating model (proposed, not commissioned)

## Lifecycle and handoff

1. **I. Inventory:** freeze signed module BOM, configuration, owners, SBOM, baselines, dependencies and evidence provenance. Current baseline exists, but signed BOM/owner assignments are missing.
2. **II. Architecture:** approve versioned contracts, trust zones, power and railway fail-safe boundaries, safety responsibility matrix, interface ownership.
3. **III. Development:** run independent module CI, reproducible builds, requirements traceability, threat modeling and change reviews.
4. **IV. Modeling:** validate digital twins against measured operating envelope and uncertainty, including degraded power, communications, rail, life support and geotechnical conditions.
5. **V. Testing:** bench and HIL; full race, restart, cross-UID, tamper, rollback, crash, latency and fault-injection matrices; mandatory independent witnesses.
6. **VI. Integration:** progressively connect read-only telemetry, then recommendations, finally explicit controlled actuation only after independent authority approval. Record regressions at every interface.
7. **VII. Operations:** operational readiness review, service manager and observability, authenticated runbooks, training, incidents, emergency evacuation, spares and independent audits.
8. **VIII. Evolution:** tightly controlled requalification, safe rollout/rollback, drift monitoring and evidence regeneration.

The lifecycle phases may overlap, but crossing a safety-critical admission boundary is **not** permitted on the basis of planning documents.

## Roles and separation of duties

- **System architecture / configuration custodian:** versioning, WBS, integration change impact.
- **Subsystem owners:** implementation, module CI, proof obligations; no unilateral ecosystem GO.
- **Independent security/witness authority:** signed monotonic release and event attestation, OS policy verification.
- **Independent functional-safety reviewer:** hazard approval, cross-component safety case and test sign-off.
- **Operations supervisor:** incident response, drills, rollback and maintenance control; no silent overrides.

These are required roles, not assigned people or instantiated privileged services.

## Incident/change workflow

`DETECTED → TRIAGED → CONTAINED → EVIDENCE_PRESERVED → ROOT_CAUSE → REVIEWED_FIX → REQUALIFIED → CLOSED`. Incident snapshots require UTC, correlation ID, module revisions, immutable collection, independent chain of custody and decision ownership. Do not reenergize/restart a safety-related service merely because a probe reports PASS. Incomplete records leave the system NO-GO.

For change requests: identify interfaces and hazard impact; record expected hashes; require independent sign-off; test in isolation, simulation and HIL; deploy through bounded canary with monitored abort; separately validate rollback and updated root. Exact production automation and restart authorities are not included in v0.1.0.

## Initial integrated verification campaign

- **Campaign A**: 9-module baseline, source review, continuous BOM drift and signed supply chain.
- **Campaign B**: interface exchange tests with mismatched revisions, units, stale quality, TTL, replay and partitions.
- **Campaign C**: multi-UID service graph and mandatory MAC/LSM; root, witness, broker and clients under independently administered identities.
- **Campaign D**: corruption/fault injection across database, journal, checkpoint, CAS, permit, IPC, watchdog and hardware power boundary.
- **Campaign E**: digital twin validation, HIL, real safety interlocks, alarm response and degraded operation.
- **Campaign F**: operational acceptance, trained operators, incident exercise, maintenance and independent certifications.

Current software evidence supports **none** of these full campaigns as complete.
