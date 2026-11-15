# RAIL-SIM-001 — Isolated deterministic digital twin (v0.6)

## Scope
An intentionally simplified, in-memory, fixed-time-step 1D train motion simulator for reproducible **software** experiments. `Decimal` SI quantities, immutable state/track records, deterministic event traces, segment speed checks, rejection of unsafe boundary transitions, atomic failure behavior.

## Interface
`TrackSegment(identifier, length_m, speed_limit_mps)`; `SimulationState(elapsed_s, position_m, velocity_mps)`; `DigitalTwin(segments, step_s='1', initial=None)`; `step(acceleration_mps2)`, `run(actions)`, `snapshot()`, `events`.

## Assumptions and limitations
The motion model is trapezoidal fixed-step kinematics, with immediate velocity clamping to zero when deceleration would produce negative speed. It is **not** a physically validated train dynamics or braking model. Speed limits are checked conservatively using the final step speed at traversed boundaries, but there is no continuous-time collision avoidance, signaling authority, grade, adhesion, train length, switch geometry, braking curve, or infrastructure physics. This is not a safety case. The simulator has no hardware or TrainOS transport connection. Do not use for dispatch, protection, or actuation.

## Acceptance evidence
`python -m unittest discover -s tests -v`: baseline 68 tests plus 18 new simulation tests. Independent validation, model calibration, safety review, and real integration remain pending.
