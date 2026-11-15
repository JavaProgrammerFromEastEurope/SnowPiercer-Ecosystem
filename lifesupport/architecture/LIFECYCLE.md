# LIFE-CORE-003 — Lifecycle Architecture

## Scope
Offline deterministic state-transition engine for logical component records. No hardware access, no command dispatch, no physical safety authorization. Registry schema v1.0 is unchanged.

## State transition table
| From | Allowed targets |
|---|---|
| REGISTERED | INITIALIZING, ISOLATED |
| INITIALIZING | STANDBY, FAULT, ISOLATED |
| STANDBY | ACTIVE, MAINTENANCE, FAULT, ISOLATED |
| ACTIVE | STANDBY, DEGRADED, FAULT, ISOLATED |
| DEGRADED | STANDBY, FAULT, ISOLATED |
| FAULT | ISOLATED, MAINTENANCE |
| ISOLATED | MAINTENANCE, INITIALIZING |
| MAINTENANCE | INITIALIZING, ISOLATED |

## Guards
ACTIVE entry requires all direct registry dependencies ACTIVE. ACTIVE exit requires all direct ACTIVE dependents to exit ACTIVE first. This guard is deliberately conservative and may block emergency transitions in the simulation; it is **not suitable for real-world protective actions**. A real safety controller must isolate faulty equipment independently, including during dependency failures.

## Audit
Events are immutable frozen Python records, ordered by a sequence and chained with SHA-256 over canonical JSON. Hash chaining detects accidental or naive modification during in-memory verification; it does not provide authenticity, tamper resistance against an adversary, durable storage, or nonrepudiation. `verify_audit()` checks local event chain and replayed state. No persistence, signing, or secure clock are implemented.

## Concurrency
Single-process, single-threaded simulation only. There is no locking, transaction isolation, persistent event store, or distributed coordination. Timestamp ordering uses UTC instants. No external schema validator dependency is bundled.

## Interface
`Lifecycle(registry)`, `.state(id)`, `.snapshot()`, `.transition(id, target, event_id=..., reason=..., actor=..., timestamp_utc=...)`, `.events`, `.verify_audit()`.

## Integration boundary
No changes to `Registry`, `validate_envelope`, existing JSON registry, or TrainOS adapters. New JSON Schemas are documentation contracts, not active validation of received network messages. `LifeCommand` remains disabled by the inherited envelope validator.
