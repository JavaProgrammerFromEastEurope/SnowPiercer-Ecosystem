# RAIL-IF-001 — TrainOS Integration Contracts

Status: implemented locally; external TrainOS integration **not performed**; review pending.

## Scope
- Versioned read-only envelope: `schema_version`, `message_id`, `kind`, `source`, `timestamp`, `payload`.
- Strict allowlist of observation types: telemetry, health and audit.
- Trusted-caller identity matching, role authorization, freshness, size limits, payload shape validation, replay rejection and append-only-in-process audit records.
- Invalid messages rejected with `ContractError`. No transport, networking, hardware adapters or actuation.

## Limitations and safety
- Caller-provided authenticated identity is a **trust assumption**. No cryptographic authentication or TrainOS identity integration.
- Replay set and audit log are process-local, unbounded, non-persistent and not concurrency-safe; unsuitable for production.
- No distributed time synchronization, durable delivery, schema negotiation, threat model review, or independent safety assessment.
- A valid observation is not a movement authority and must never be interpreted as permission to actuate.
- This Stage is a contract prototype only; operational readiness remains NO-GO.

## Acceptance
Run `python -m unittest discover -s tests -v` from repository root. Record output, Python version and test counts. Independent contract and safety review outstanding.
