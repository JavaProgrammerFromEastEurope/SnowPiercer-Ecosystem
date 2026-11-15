import itertools
from concurrent.futures import ThreadPoolExecutor
import pytest
from energy import (EnergyMode, EnergyError, OperatingProfile, StateCommand, EnergyStateController)


def cmd(n, target, **kw):
    return StateCommand(f'id-{n}', n, target, **kw)


def test_initial_state():
    c = EnergyStateController()
    assert c.snapshot.mode == EnergyMode.OFF
    assert c.snapshot.sequence == 0
    assert c.events == ()


def test_normal_path_and_profiles():
    c = EnergyStateController()
    c.apply(cmd(1, EnergyMode.STANDBY, profile=OperatingProfile.MAINTENANCE))
    assert c.snapshot.profile == OperatingProfile.MAINTENANCE
    c.apply(cmd(2, EnergyMode.SIMULATION))
    assert c.snapshot.profile == OperatingProfile.TRAINING
    c.apply(cmd(3, EnergyMode.STANDBY))
    c.apply(cmd(4, EnergyMode.OFF))
    assert len(c.events) == 4


@pytest.mark.parametrize('origin,target', list(itertools.product(EnergyMode, repeat=2)))
def test_exhaustive_transition_matrix(origin, target):
    c = EnergyStateController()
    if origin == EnergyMode.STANDBY:
        c.apply(cmd(1, EnergyMode.STANDBY))
    elif origin == EnergyMode.SIMULATION:
        c.apply(cmd(1, EnergyMode.STANDBY))
        c.apply(cmd(2, EnergyMode.SIMULATION))
    elif origin == EnergyMode.FAULT:
        c.apply(cmd(1, EnergyMode.FAULT))
    before = c.snapshot
    command = cmd(before.sequence + 1, target)
    if target in c.allowed_transitions(origin) and origin != EnergyMode.FAULT:
        c.apply(command)
        assert c.snapshot.mode == target
    else:
        with pytest.raises(EnergyError):
            c.apply(command)
        assert c.snapshot == before


def test_fault_recovery_requires_attestation_and_one_time_permit():
    c = EnergyStateController()
    c.apply(cmd(1, EnergyMode.FAULT))
    with pytest.raises(EnergyError):
        c.issue_recovery_permit(inspection_passed=False)
    with pytest.raises(EnergyError):
        c.apply(cmd(2, EnergyMode.OFF))
    token = c.issue_recovery_permit(inspection_passed=True)
    with pytest.raises(EnergyError):
        c.apply(cmd(2, EnergyMode.OFF, recovery_permit='fake'))
    c.apply(cmd(2, EnergyMode.OFF, recovery_permit=token))
    with pytest.raises(EnergyError):
        c.apply(cmd(3, EnergyMode.STANDBY, recovery_permit=token))
    c.apply(cmd(3, EnergyMode.FAULT))
    with pytest.raises(EnergyError):
        c.apply(cmd(4, EnergyMode.OFF, recovery_permit=token))
    assert c.snapshot.fault_epoch == 2


@pytest.mark.parametrize('bad', [0, -1, True, 1.5, '2'])
def test_bad_sequences(bad):
    with pytest.raises(EnergyError):
        StateCommand('id', bad, EnergyMode.OFF)


def test_invalid_commands_do_not_mutate():
    c = EnergyStateController()
    c.apply(cmd(1, EnergyMode.STANDBY))
    before = c.snapshot
    for bad in [cmd(1, EnergyMode.OFF), cmd(3, EnergyMode.OFF), cmd(2, EnergyMode.STANDBY), cmd(2, EnergyMode.SIMULATION, profile=OperatingProfile.ISOLATED)]:
        with pytest.raises(EnergyError):
            c.apply(bad)
        assert c.snapshot == before
        assert len(c.events) == 1


def test_thread_race_single_winner():
    c = EnergyStateController()
    commands = [StateCommand(f'race-{i}', 1, EnergyMode.STANDBY) for i in range(32)]
    def attempt(command):
        try:
            c.apply(command)
            return True
        except EnergyError:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, commands))
    assert sum(results) == 1
    assert c.snapshot.sequence == 1
    assert len(c.events) == 1


def test_exhaustive_short_command_sequences():
    for targets in itertools.product(EnergyMode, repeat=4):
        c = EnergyStateController()
        for i, target in enumerate(targets, 1):
            previous = c.snapshot
            try:
                after = c.apply(cmd(i, target))
                assert target in c.allowed_transitions(previous.mode)
                assert previous.mode != EnergyMode.FAULT
                assert after.sequence == previous.sequence + 1
            except EnergyError:
                assert c.snapshot == previous
                break
        assert all(e.before.sequence + 1 == e.after.sequence for e in c.events)
        assert all(e.after.mode in c.allowed_transitions(e.before.mode) for e in c.events)


def test_no_actuation_and_legacy_compatibility():
    from energy import EnergySystem, Asset, AssetKind
    s = EnergySystem()
    s.register(Asset('generator', AssetKind.SOURCE, 2))
    s.transition(EnergyMode.STANDBY)
    assert s.mode == EnergyMode.STANDBY
    assert not hasattr(EnergyStateController(), 'energize')
