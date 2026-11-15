import pytest
from energy import Asset, AssetKind, EnergyMode, EnergySystem, EnergyError, PowerRequest, IntegrationEnvelope


def test_allocation_critical_first():
    s = EnergySystem()
    for a in (Asset('g', AssetKind.SOURCE, 5), Asset('ordinary', AssetKind.CONSUMER, 5), Asset('life', AssetKind.CONSUMER, 4, critical=True)):
        s.register(a)
    s.transition(EnergyMode.STANDBY)
    s.transition(EnergyMode.SIMULATION)
    assert [(a.consumer_id, a.granted_kw) for a in s.simulate_allocation([PowerRequest('ordinary', 5), PowerRequest('life', 4)])] == [('life', 4), ('ordinary', 1)]
    assert s.mode == EnergyMode.SIMULATION

@pytest.mark.parametrize('asset', [
    Asset('x', AssetKind.SOURCE, 1),
    Asset('s', AssetKind.STORAGE, 2, capacity_kwh=4, stored_kwh=3),
    Asset('c', AssetKind.CONVERTER, 2, efficiency=.9),
    Asset('l', AssetKind.CONSUMER, 2, critical=True),
])
def test_asset_kinds(asset):
    assert asset.rated_kw >= 0

@pytest.mark.parametrize('kwargs', [
    dict(asset_id='', kind=AssetKind.SOURCE, rated_kw=1),
    dict(asset_id='a', kind=AssetKind.SOURCE, rated_kw=-1),
    dict(asset_id='a', kind=AssetKind.SOURCE, rated_kw=float('nan')),
    dict(asset_id='a', kind=AssetKind.STORAGE, rated_kw=1, capacity_kwh=1, stored_kwh=2),
    dict(asset_id='a', kind=AssetKind.CONVERTER, rated_kw=1, efficiency=0),
    dict(asset_id='a', kind=AssetKind.SOURCE, rated_kw=1, critical=True),
    dict(asset_id='a', kind=AssetKind.CONSUMER, rated_kw=True),
])
def test_reject_invalid_asset(kwargs):
    with pytest.raises(EnergyError):
        Asset(**kwargs)

def test_fail_closed_mode_and_duplicates():
    s = EnergySystem()
    with pytest.raises(EnergyError):
        s.simulate_allocation([])
    with pytest.raises(EnergyError):
        s.transition(EnergyMode.SIMULATION)
    s.register(Asset('x', AssetKind.CONSUMER, 1))
    with pytest.raises(EnergyError):
        s.register(Asset('x', AssetKind.CONSUMER, 1))
    s.transition(EnergyMode.STANDBY)
    s.transition(EnergyMode.SIMULATION)
    with pytest.raises(EnergyError):
        s.simulate_allocation([PowerRequest('x', 1), PowerRequest('x', 1)])
    with pytest.raises(EnergyError):
        s.simulate_allocation([PowerRequest('x', 2)])
    with pytest.raises(EnergyError):
        s.register(Asset('y', AssetKind.SOURCE, 2))
    s.transition(EnergyMode.FAULT)
    with pytest.raises(EnergyError):
        s.transition(EnergyMode.SIMULATION)
    s.transition(EnergyMode.OFF)

def test_integration_contracts():
    for subsystem in ('TrainOS', 'AI', 'Rail', 'LifeSupport', 'Security'):
        assert IntegrationEnvelope(subsystem, 1, 'test', {'intent': 'observe'}).subsystem == subsystem
    with pytest.raises(EnergyError):
        IntegrationEnvelope('untrusted', 1, 'x', {})
    with pytest.raises(EnergyError):
        IntegrationEnvelope('AI', 2, 'x', {})

def test_no_hardware_api():
    assert not hasattr(EnergySystem(), 'energize')
    assert not hasattr(EnergySystem(), 'write_actuator')
