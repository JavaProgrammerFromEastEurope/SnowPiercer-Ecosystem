"""Deterministic, conservative simulation-only power and energy accounting."""
from dataclasses import dataclass
from math import isfinite, fsum
from typing import Tuple
from .domain import Asset, AssetKind, EnergyError, PowerRequest, EnergySystem, EnergyMode


def finite(value, name, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0 or (positive and value == 0):
        raise EnergyError(f'{name} must be finite and {"positive" if positive else "nonnegative"}')
    return float(value)

@dataclass(frozen=True)
class StorageDispatch:
    asset_id: str
    discharge_kw: float = 0.0  # delivered to bus, after efficiency
    charge_kw: float = 0.0     # drawn from bus, before efficiency
    def __post_init__(self):
        if not isinstance(self.asset_id, str) or not self.asset_id.strip(): raise EnergyError('invalid storage id')
        finite(self.discharge_kw, 'discharge_kw'); finite(self.charge_kw, 'charge_kw')
        if self.discharge_kw and self.charge_kw: raise EnergyError('simultaneous charge/discharge denied')

@dataclass(frozen=True)
class PowerLedger:
    duration_h: float
    generation_kw: float
    discharge_kw: float
    charge_kw: float
    delivered_kw: float
    curtailed_kw: float
    unserved_kw: float
    reserve_kw: float
    allocations: Tuple[tuple[str, float], ...]
    storage_after: Tuple[tuple[str, float], ...]
    simulated: bool = True


def account(system: EnergySystem, requests: tuple[PowerRequest, ...], *, duration_h: float,
            dispatch: tuple[StorageDispatch, ...] = (), reserve_kw: float = 0.0) -> PowerLedger:
    """One immutable snapshot. No mutation, hardware I/O, or persistence.

    Reserve is held back from load, charge and curtailment; it is NOT consumed.
    Charge/discharge dispatch is explicit; no automatic storage scheduling.
    """
    if not isinstance(system, EnergySystem) or system.mode != EnergyMode.SIMULATION:
        raise EnergyError('simulation mode required')
    duration_h = finite(duration_h, 'duration_h', positive=True)
    reserve_kw = finite(reserve_kw, 'reserve_kw')
    if not isinstance(requests, (tuple, list)) or not isinstance(dispatch, (tuple, list)):
        raise EnergyError('requests and dispatch must be sequences')
    if any(not isinstance(r, PowerRequest) for r in requests) or any(not isinstance(d, StorageDispatch) for d in dispatch):
        raise EnergyError('invalid request or dispatch')
    ids = [r.consumer_id for r in requests]
    dids = [d.asset_id for d in dispatch]
    if len(set(ids)) != len(ids) or len(set(dids)) != len(dids): raise EnergyError('duplicate IDs')
    for r in requests:
        a = system.assets.get(r.consumer_id)
        if a is None or a.kind != AssetKind.CONSUMER or r.kw > a.rated_kw:
            raise EnergyError('invalid consumer request')
    after = []
    for d in sorted(dispatch, key=lambda x: x.asset_id):
        a = system.assets.get(d.asset_id)
        if a is None or a.kind != AssetKind.STORAGE: raise EnergyError('unknown storage')
        if d.discharge_kw > a.rated_kw or d.charge_kw > a.rated_kw: raise EnergyError('storage rating exceeded')
        new = a.stored_kwh + d.charge_kw * duration_h * a.efficiency - d.discharge_kw * duration_h / a.efficiency
        if not isfinite(new) or new < -1e-9 or new > a.capacity_kwh + 1e-9:
            raise EnergyError('storage energy boundary exceeded')
        after.append((d.asset_id, min(a.capacity_kwh, max(0.0, new))))
    generation = finite(fsum(a.rated_kw for a in system.assets.values() if a.kind == AssetKind.SOURCE), 'generation')
    discharge = finite(fsum(d.discharge_kw for d in dispatch), 'discharge')
    charge = finite(fsum(d.charge_kw for d in dispatch), 'charge')
    available = finite(generation + discharge, 'available')
    if charge + reserve_kw > available + 1e-9: raise EnergyError('charge plus reserve exceeds supply')
    remaining = max(0.0, available - charge - reserve_kw)
    allocations = []
    for r in sorted(requests, key=lambda r: (not system.assets[r.consumer_id].critical, r.consumer_id)):
        grant = min(r.kw, remaining)
        allocations.append((r.consumer_id, grant))
        remaining = max(0.0, remaining - grant)
    delivered = finite(fsum(v for _, v in allocations), 'delivered')
    requested = finite(fsum(r.kw for r in requests), 'requested')
    curtailed = finite(available - charge - reserve_kw - delivered, 'curtailed')
    unserved = finite(requested - delivered, 'unserved')
    # The tolerance is strictly floating-point roundoff, not an allowed power imbalance.
    if not isfinite(fsum((generation, discharge, -charge, -reserve_kw, -delivered, -curtailed))):
        raise EnergyError('nonfinite balance')
    return PowerLedger(duration_h, generation, discharge, charge, delivered, curtailed,
                       unserved, reserve_kw, tuple(allocations), tuple(after))
