"""Isolated, deterministic *toy* rail motion model. NOT for train control.

All quantities are SI Decimal values. Fixed-step constant acceleration is a
simplification, not a validated braking or traction model.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Tuple


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, str, Decimal)):
        raise ValueError('quantity must be int, decimal string, or Decimal')
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError('invalid quantity') from None
    if not result.is_finite():
        raise ValueError('quantity must be finite')
    return result


@dataclass(frozen=True)
class TrackSegment:
    identifier: str
    length_m: Decimal
    speed_limit_mps: Decimal

    def __post_init__(self):
        if not isinstance(self.identifier, str) or not self.identifier.strip():
            raise ValueError('segment identifier required')
        for name in ('length_m', 'speed_limit_mps'):
            object.__setattr__(self, name, number(getattr(self, name)))
        if self.length_m <= 0 or self.speed_limit_mps <= 0:
            raise ValueError('segment length and limit must be positive')


@dataclass(frozen=True)
class SimulationState:
    elapsed_s: Decimal = Decimal('0')
    position_m: Decimal = Decimal('0')
    velocity_mps: Decimal = Decimal('0')

    def __post_init__(self):
        for name in ('elapsed_s', 'position_m', 'velocity_mps'):
            object.__setattr__(self, name, number(getattr(self, name)))
        if min(self.elapsed_s, self.position_m, self.velocity_mps) < 0:
            raise ValueError('negative state quantity')


@dataclass(frozen=True)
class SimulationEvent:
    step: int
    kind: str
    elapsed_s: Decimal
    position_m: Decimal
    velocity_mps: Decimal


class SimulationError(ValueError):
    pass


class DigitalTwin:
    """No I/O, no hardware handles, no TrainOS command channel."""

    def __init__(self, segments: Tuple[TrackSegment, ...], step_s='1', initial=None):
        if not isinstance(segments, (tuple, list)) or not segments:
            raise SimulationError('nonempty track required')
        if not all(isinstance(s, TrackSegment) for s in segments):
            raise SimulationError('invalid track segment')
        if len({s.identifier for s in segments}) != len(segments):
            raise SimulationError('duplicate segment identifiers')
        self.segments = tuple(segments)
        self.step_s = number(step_s)
        if self.step_s <= 0:
            raise SimulationError('step must be positive')
        self.total_length_m = sum((s.length_m for s in self.segments), Decimal(0))
        self.state = initial if initial is not None else SimulationState()
        if not isinstance(self.state, SimulationState):
            raise SimulationError('invalid initial state')
        if self.state.position_m > self.total_length_m:
            raise SimulationError('initial position beyond track')
        if self.state.velocity_mps > self._limit_at(self.state.position_m):
            raise SimulationError('initial speed exceeds limit')
        if self.state.position_m == self.total_length_m and self.state.velocity_mps != 0:
            raise SimulationError('terminal speed must be zero')
        self.events = ()

    def _limit_at(self, position):
        distance = Decimal(0)
        for segment in self.segments:
            distance += segment.length_m
            if position < distance:
                return segment.speed_limit_mps
        return self.segments[-1].speed_limit_mps

    def step(self, acceleration_mps2='0'):
        """Atomic step; reject any overspeed, segment boundary crossing at overspeed,
        or nonzero-velocity movement past end. No partial state changes on failure.
        """
        a = number(acceleration_mps2)
        old = self.state
        dt = self.step_s
        new_v = old.velocity_mps + a * dt
        if new_v < 0:
            new_v = Decimal(0)
        # Trapezoidal distance; simplified fixed-step kinematics.
        new_p = old.position_m + (old.velocity_mps + new_v) * dt / 2
        if new_p > self.total_length_m:
            raise SimulationError('track boundary exceeded')
        # Check all segment limits traversed, including exact boundary entry.
        checkpoints = [old.position_m, new_p]
        boundary = Decimal(0)
        for segment in self.segments[:-1]:
            boundary += segment.length_m
            if old.position_m <= boundary <= new_p:
                checkpoints.append(boundary)
        if any(new_v > self._limit_at(p) for p in checkpoints):
            raise SimulationError('speed limit exceeded')
        if new_p == self.total_length_m and new_v != 0:
            raise SimulationError('train must stop at end of track')
        new_state = SimulationState(old.elapsed_s + dt, new_p, new_v)
        event = SimulationEvent(len(self.events) + 1, 'step', new_state.elapsed_s,
                                new_state.position_m, new_state.velocity_mps)
        self.state = new_state
        self.events += (event,)
        return new_state

    def run(self, accelerations):
        for acceleration in accelerations:
            self.step(acceleration)
        return self.state

    def snapshot(self):
        return {'elapsed_s': str(self.state.elapsed_s),
                'position_m': str(self.state.position_m),
                'velocity_mps': str(self.state.velocity_mps),
                'events': len(self.events)}
