# RailSystem architecture v0.1

## Domains
- rolling_stock: vehicles, consist composition, telemetry
- infrastructure: track, switches, stations, depots
- traffic: timetables, dispatching, route requests
- signaling_safety: interlocking boundary, movement authority, emergency state
- traction_braking: traction and brake status interfaces
- maintenance: condition monitoring and work orders
- digital_twin: simulation scenarios and replay
- operations: audit events, operator workflows

## Boundaries
TrainOS: authentication, message transport, telemetry and audit adapters (contract TBD).
Energy: traction supply and isolation (contract TBD).
Security: identity, authorization and incident response (contract TBD).
AI: advisory predictions only; no autonomous safety authority.
Logistics: cargo and resource scheduling.
SnowPiercer Island: physical site and depot integration.

## Safety principles
No live actuator commands in this scaffold. An unavailable/invalid authority must never be interpreted as permission to move. Separate supervisory decision support from certified interlocking and train protection.

## Standards to assess for applicable jurisdiction
EN 50126, EN 50128/EN 50716, EN 50129, EN 50159, IEC 62443 and relevant national railway rules; applicability requires formal assessment.
