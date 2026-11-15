# ENERGY-CORE-002 — Energy State Machine & Operating Modes

Status: software unit verification only; **physical deployment NO-GO**.

## Requirements / verification traceability

| ID | Contract / requirement | Test |
|---|---|---|
| EN2-001 | Preserve all ENERGY-CORE-001 public imports and legacy transitions | test_no_actuation_and_legacy_compatibility, test_domain.py |
| EN2-002 | Explicit legal mode transition relation, reject self-transitions | test_exhaustive_transition_matrix |
| EN2-003 | Constrain operating profile to target mode | test_normal_path_and_profiles, test_invalid_commands_do_not_mutate |
| EN2-004 | Fail closed on duplicate, stale, out-of-order commands | test_invalid_commands_do_not_mutate, test_bad_sequences |
| EN2-005 | Latch FAULT; reset only to OFF after local inspection attestation and matching permit | test_fault_recovery_requires_attestation_and_one_time_permit |
| EN2-006 | Atomic in-process transition and immutable event snapshots | test_thread_race_single_winner |
| EN2-007 | Explore all short paths of depth four | test_exhaustive_short_command_sequences |
| EN2-008 | No hardware actuation API | test_no_actuation_and_legacy_compatibility |

## Architecture / contracts

`energy.domain` is retained unchanged. `energy.state_machine` adds `EnergyStateController`, `StateCommand`, `StateSnapshot`, `StateEvent`, `OperatingProfile`. Existing `EnergySystem.transition()` retains its original semantics, intentionally: new guards apply only when using `EnergyStateController`. Consumers must explicitly migrate to the guarded controller; this is **not** a mandatory admission boundary.

State graph: OFF -> STANDBY / FAULT; STANDBY -> OFF / SIMULATION / FAULT; SIMULATION -> STANDBY / FAULT; FAULT -> OFF only with locally issued recovery permit. Self-transitions are rejected. A rejected command must not change snapshot, sequence, or event log. A successful command consumes exactly one next sequence and unique command_id. Invalid commands do not consume sequence numbers. FAULT increments fault_epoch; permit expires on any successful transition and cannot be reused across fault epochs.

Profiles: OFF and FAULT -> ISOLATED; STANDBY -> OBSERVATION or MAINTENANCE; SIMULATION -> TRAINING. Profile selection is explicit on a transition; there is no implicit in-place profile mutation.

Integration boundaries (TrainOS, AI / Cognition, Rail Systems, Life Support, Security) remain the v1 `IntegrationEnvelope` defined in ENERGY-CORE-001. These are schema-level only; no authentication, transport, replay defense across process restarts, or operational actuation. AI must remain advisory. No direct actuator access is exposed.

## Safety analysis

| Hazard | Mitigation tested | Residual limitation |
|---|---|---|
| H2-01 Unauthorized transition | Enumerated transition graph | No authenticated command principal |
| H2-02 Accidental recovery from fault | FAULT latch and local permit | Permit is predictable, local and self-attested; not a trust boundary |
| H2-03 Duplicate/replayed command | ID + strict sequence checks | Volatile memory; restart resets history |
| H2-04 Concurrent commands | RLock protects state/event update | No cross-process locking or durable commit |
| H2-05 Invalid profile | Mode/profile compatibility | No physical operating mode validation |
| H2-06 Legacy bypass | Existing API compatibility preserved | Legacy `EnergySystem.transition` does not enforce new permits |
| H2-07 Unexpected process death | None | No durable recovery, journaling or crash-consistency proof |

## Admission decision

**NO-GO** for physical deployment and production safety control. No independent end-to-end evidence, physical I/O, verified external interlocks, durable state or multi-UID authorization. Only in-process model properties and local tests are evidenced.
