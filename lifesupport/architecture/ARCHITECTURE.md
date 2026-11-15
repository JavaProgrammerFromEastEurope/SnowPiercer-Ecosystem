# LIFE-CORE-002 architecture

Boundary: offline registry, dependency graph, requirement traceability and non-actuating message-envelope validator.
Inputs: versioned JSON registry and example message objects.
Outputs: validation results, dependency ordering, requirement traces and test evidence.
Not in scope: sensors, actuators, plant control, remote communications, physiological monitoring or certification.

## Dependencies
Each of the 19 domain reference components depends on LIFE-CORE-001; dependencies are directed, acyclic and resolved before use.
This is an *information-model dependency*, not a physical redundancy or power architecture.

## Integration
TrainOS is an external consumer of versioned metadata. No TrainOS source is modified.
LifeCommand is reserved in the schema but unconditionally rejected by this implementation.
Production message contracts require authentication, authorization, anti-replay, freshness, semantic payload validation, bounded resource usage and fail-safe handling.
