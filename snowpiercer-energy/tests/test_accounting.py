import itertools
import math
import pytest
from energy import (Asset, AssetKind, EnergySystem, EnergyMode, PowerRequest,
                    StorageDispatch, EnergyError, account)

def system(source=10, stored=5):
    s = EnergySystem()
    s.register(Asset('source', AssetKind.SOURCE, source))
    s.register(Asset('battery', AssetKind.STORAGE, 5, capacity_kwh=10, stored_kwh=stored, efficiency=.8))
    s.register(Asset('critical', AssetKind.CONSUMER, 12, critical=True))
    s.register(Asset('ordinary', AssetKind.CONSUMER, 12))
    s.transition(EnergyMode.STANDBY)
    s.transition(EnergyMode.SIMULATION)
    return s

def test_priority_and_balance():
    s = system()
    l = account(s, (PowerRequest('ordinary', 8), PowerRequest('critical', 9)), duration_h=1, reserve_kw=2)
    assert l.allocations == (('critical', 8), ('ordinary', 0))
    assert l.unserved_kw == 9
    assert math.isclose(l.generation_kw + l.discharge_kw, l.delivered_kw + l.charge_kw + l.reserve_kw + l.curtailed_kw, abs_tol=1e-9)

def test_storage_discharge_and_charge():
    s = system()
    l = account(s, (PowerRequest('critical', 12),), duration_h=1, dispatch=(StorageDispatch('battery', discharge_kw=4),))
    assert l.storage_after == (('battery', 0),)
    assert l.delivered_kw == 12
    c = account(s, (), duration_h=1, dispatch=(StorageDispatch('battery', charge_kw=5),))
    assert c.storage_after == (('battery', 9),)
    assert s.assets['battery'].stored_kwh == 5

@pytest.mark.parametrize('d', [StorageDispatch('battery', discharge_kw=5), StorageDispatch('battery', charge_kw=5)])
def test_invalid_storage_energy(d):
    with pytest.raises(EnergyError): account(system(stored=0 if d.discharge_kw else 10), (), duration_h=1, dispatch=(d,))

@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -1, True, 0])
def test_invalid_duration(bad):
    with pytest.raises(EnergyError): account(system(), (), duration_h=bad)

@pytest.mark.parametrize('reserve', [-1, float('nan'), float('inf'), 100])
def test_invalid_reserve(reserve):
    with pytest.raises(EnergyError): account(system(), (), duration_h=1, reserve_kw=reserve)

def test_duplicate_and_invalid_dispatch():
    s = system()
    with pytest.raises(EnergyError): account(s, (), duration_h=1, dispatch=(StorageDispatch('battery'), StorageDispatch('battery')))
    with pytest.raises(EnergyError): account(s, (), duration_h=1, dispatch=(StorageDispatch('missing'),))
    with pytest.raises(EnergyError): StorageDispatch('battery', charge_kw=1, discharge_kw=1)

def test_exhaustive_small_domain():
    count = 0
    for supply, critical, ordinary, reserve in itertools.product(range(5), repeat=4):
        s = system(source=supply)
        req = (PowerRequest('ordinary', ordinary), PowerRequest('critical', critical))
        if reserve > supply:
            with pytest.raises(EnergyError): account(s, req, duration_h=1, reserve_kw=reserve)
            continue
        l = account(s, req, duration_h=1, reserve_kw=reserve)
        grants = dict(l.allocations)
        assert grants['critical'] == min(critical, supply - reserve)
        assert grants['ordinary'] == min(ordinary, max(0, supply - reserve - critical))
        assert math.isclose(l.generation_kw, l.delivered_kw + l.curtailed_kw + l.reserve_kw, abs_tol=1e-9)
        assert math.isclose(l.unserved_kw, critical + ordinary - l.delivered_kw, abs_tol=1e-9)
        count += 1
    assert count == 375

def test_permutation_invariance():
    s = system()
    req = [PowerRequest('ordinary', 8), PowerRequest('critical', 9)]
    assert account(s, req, duration_h=1) == account(s, req[::-1], duration_h=1)

def test_mode_fence():
    with pytest.raises(EnergyError): account(EnergySystem(), (), duration_h=1)
