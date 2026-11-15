"""Simulation-only, in-memory supervisory FSM. Not an authorization boundary."""
from dataclasses import dataclass
from enum import Enum
from threading import RLock
from typing import Optional
from .domain import EnergyError, EnergyMode

class OperatingProfile(str, Enum):
    ISOLATED = 'isolated'
    OBSERVATION = 'observation'
    TRAINING = 'training'
    MAINTENANCE = 'maintenance'

_ALLOWED = {
    EnergyMode.OFF: frozenset((EnergyMode.STANDBY, EnergyMode.FAULT)),
    EnergyMode.STANDBY: frozenset((EnergyMode.OFF, EnergyMode.SIMULATION, EnergyMode.FAULT)),
    EnergyMode.SIMULATION: frozenset((EnergyMode.STANDBY, EnergyMode.FAULT)),
    EnergyMode.FAULT: frozenset((EnergyMode.OFF,)),
}
_PROFILES = {
    EnergyMode.OFF: frozenset((OperatingProfile.ISOLATED,)),
    EnergyMode.STANDBY: frozenset((OperatingProfile.OBSERVATION, OperatingProfile.MAINTENANCE)),
    EnergyMode.SIMULATION: frozenset((OperatingProfile.TRAINING,)),
    EnergyMode.FAULT: frozenset((OperatingProfile.ISOLATED,)),
}
_DEFAULT = {EnergyMode.OFF: OperatingProfile.ISOLATED,
            EnergyMode.STANDBY: OperatingProfile.OBSERVATION,
            EnergyMode.SIMULATION: OperatingProfile.TRAINING,
            EnergyMode.FAULT: OperatingProfile.ISOLATED}

@dataclass(frozen=True)
class StateCommand:
    command_id: str
    sequence: int
    target: EnergyMode
    profile: Optional[OperatingProfile] = None
    recovery_permit: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.command_id, str) or not self.command_id.strip():
            raise EnergyError('command_id required')
        if type(self.sequence) is not int or self.sequence < 1:
            raise EnergyError('positive integer sequence required')
        if not isinstance(self.target, EnergyMode):
            raise EnergyError('invalid target')
        if self.profile is not None and not isinstance(self.profile, OperatingProfile):
            raise EnergyError('invalid profile')
        if self.recovery_permit is not None and (not isinstance(self.recovery_permit, str) or not self.recovery_permit):
            raise EnergyError('invalid recovery permit')

@dataclass(frozen=True)
class StateSnapshot:
    mode: EnergyMode
    profile: OperatingProfile
    sequence: int
    fault_epoch: int
    fault_latched: bool

@dataclass(frozen=True)
class StateEvent:
    command_id: str
    before: StateSnapshot
    after: StateSnapshot

class EnergyStateController:
    """Strict FSM; all operations atomic only within this Python process."""
    def __init__(self):
        self._lock = RLock()
        self._snapshot = StateSnapshot(EnergyMode.OFF, OperatingProfile.ISOLATED, 0, 0, False)
        self._seen = set()
        self._events = []
        self._permit = None
        self._permit_counter = 0

    @property
    def snapshot(self) -> StateSnapshot:
        with self._lock:
            return self._snapshot

    @property
    def events(self) -> tuple[StateEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def issue_recovery_permit(self, *, inspection_passed: bool) -> str:
        """Local test attestation only; NOT authenticated or suitable for production."""
        with self._lock:
            if type(inspection_passed) is not bool or not inspection_passed or self._snapshot.mode != EnergyMode.FAULT:
                raise EnergyError('inspection required in fault state')
            self._permit_counter += 1
            self._permit = f'local-{self._snapshot.fault_epoch}-{self._permit_counter}'
            return self._permit

    def apply(self, command: StateCommand) -> StateSnapshot:
        with self._lock:
            if not isinstance(command, StateCommand):
                raise EnergyError('invalid command')
            before = self._snapshot
            if command.command_id in self._seen or command.sequence != before.sequence + 1:
                raise EnergyError('duplicate, stale or out-of-order command')
            if command.target not in _ALLOWED[before.mode]:
                raise EnergyError('transition denied')
            if before.mode == EnergyMode.FAULT:
                if command.target != EnergyMode.OFF or self._permit is None or command.recovery_permit != self._permit:
                    raise EnergyError('fault latched: recovery permit required')
            elif command.recovery_permit is not None:
                raise EnergyError('unexpected recovery permit')
            profile = command.profile if command.profile is not None else _DEFAULT[command.target]
            if profile not in _PROFILES[command.target]:
                raise EnergyError('profile incompatible with target')
            epoch = before.fault_epoch + (command.target == EnergyMode.FAULT)
            after = StateSnapshot(command.target, profile, command.sequence, epoch, command.target == EnergyMode.FAULT)
            self._snapshot = after
            self._seen.add(command.command_id)
            self._events.append(StateEvent(command.command_id, before, after))
            self._permit = None
            return after

    @staticmethod
    def allowed_transitions(mode: EnergyMode) -> frozenset[EnergyMode]:
        if not isinstance(mode, EnergyMode):
            raise EnergyError('invalid mode')
        return _ALLOWED[mode]
