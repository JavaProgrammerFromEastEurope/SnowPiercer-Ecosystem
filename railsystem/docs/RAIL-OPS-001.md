# RAIL-OPS-001 — Railway Operations & Route Planning

Status: implemented as a simulation-only prototype; independent design/safety review pending.

## Scope

- Immutable Station, RailLink, Journey, Reservation and Plan records.
- Directed graph with deterministic shortest nominal travel-time path selection.
- Virtual exclusive track-resource reservations with half-open time intervals.
- Atomic timetable insertion and deterministic snapshots.
- Adapter to the existing RAIL-SIM-001 DigitalTwin track segments.
- 24 new unit tests; full suite executed using Python unittest.

## Assumptions and limitations

- Times in Decimal seconds, lengths in meters, speed limits in meters per second.
- Nominal traversal time = length / speed limit, **not** physical running time.
- A link pair between the same stations is conservatively treated as the same physical resource even if the real infrastructure might have separate tracks.
- No dwell times, train length, acceleration/braking curves, occupancy margins, junction interlocking, platform allocation, maintenance windows, signaling, or route authorities.
- Route planning does not automatically find alternate routes after a reservation conflict.
- No real hardware, train control or TrainOS transport is accessed.
- The simulator adapter builds virtual segments but does not claim that planned nominal arrival times match the motion simulator.
- Validation and safety review remain open; no safety case or authorization is implied.

## Acceptance evidence

Run from project root:

```sh
python -m unittest discover -s tests -v
```

Expected at the time of this release: 110 tests pass (86 inherited + 24 new).

## Next stage

RAIL-VER-001 — reproducible regression reporting and CI readiness.
