# ENERGY-CORE-001 Requirements and traceability

| ID | Requirement | Verification |
|---|---|---|
| EN-R-001 | Model source, storage, converter, consumer with validated finite ratings | test_asset_kinds, test_reject_invalid_asset |
| EN-R-002 | Deny invalid state transitions | test_fail_closed_mode_and_duplicates |
| EN-R-003 | Allocate power deterministically to critical consumers first, never above source rating | test_allocation_critical_first |
| EN-R-004 | Deny unknown, duplicate or over-rated requests | test_fail_closed_mode_and_duplicates |
| EN-R-005 | Define versioned envelopes for five integration boundaries | test_integration_contracts |
| EN-R-006 | Expose no physical actuation API | test_no_hardware_api |

## Architecture

Pure Python `energy.domain` models assets, state machine and deterministic illustrative allocation. Storage energy, converter efficiency, network constraints, load shedding and temporal dynamics are **not** yet part of dispatch calculations. No persistent event ledger, supervisory control or authenticated transport exists.

## Integration contracts (design only)

All boundaries use `IntegrationEnvelope(subsystem, schema_version=1, correlation_id, payload)` with string/string payload. It is a validation envelope, **not** a wire protocol or security boundary.

- TrainOS: supervisory status and proposed operating intents; no direct actuator authority.
- AI: advisory forecasts and optimization proposals; cannot override safety policy.
- Rail: traction demand and regeneration telemetry, not yet implemented.
- LifeSupport: critical demand and reserve policy; priority represented by `critical` flag only.
- Security: incident and isolation intents; identity, authorization and signatures remain unimplemented.

## Safety analysis

| Hazard | Mitigation in this Stage | Residual risk |
|---|---|---|
| H-01 Over-allocation | Cap simulated grants to sum of nominal source ratings | No grid loss, derating or source availability modeling |
| H-02 Invalid commands | Mode transitions and input validation reject invalid requests | No authenticated runtime control path |
| H-03 Loss of critical power | Critical-first deterministic allocation | No physical failover or assured reserve |
| H-04 Untrusted subsystem message | Version and field validation | No cryptographic authentication or replay protection |
| H-05 Physical unsafe actuation | No actuator interface | Cannot demonstrate hardware safety |

## Admission decision

**NO-GO** for physical operations, safety certification and production control. Independent HIL/E2E evidence, fault injection, threat analysis, hardware isolation and qualified review are absent.
