# LOG-CORE-021 integration contract

`TimedLogisticsLedger(path, clock_ms=trusted_callable)` accepts host-supplied
epoch milliseconds. The default uses `time.time_ns() // 1_000_000`.

`execute_envelope(trusted_principal, envelope)` consumes exactly:

```json
{
  "schema_version": 1,
  "command_id": "trainos-command-unique-id",
  "issued_at_ms": 1000,
  "ttl_ms": 1000,
  "expected_events": 0,
  "action": "add_location",
  "args": {"location_id": "warehouse-a", "kind": "warehouse"}
}
```

The sample is valid only with a compatible test clock, not the current wall
clock. Version, timestamps, TTL and revision must be integers (booleans are
rejected). TTL is positive and bounded to 86,400,000 ms. Requests issued in the
future or at/after their deadline fail before mutation.

Actions: `add_container`, `add_location`, `register_cargo`, `transition_cargo`,
`create_mission`, `transition_mission`, `record_transfer`. Each action has an
exact required argument set matching its existing typed model. Additional
envelope/argument fields are rejected. There is no wire-supplied principal,
role, production certification or recovery action.

Malformed, expired and unsupported requests raise `AdmissionError`. Revision,
replay-fingerprint and legacy-key conflicts raise `ConflictError`. Existing
permission and cargo invariants retain their original exceptions. A failure
does not create a successful receipt. `production_admission()` always raises.

`integration_probe.py --correlation-id STRING` uses a temporary SQLite model
and emits one `snowpiercer.integration-probe.v1` JSON result. Its
`operationalReady` is always false; probe success is not physical readiness.
