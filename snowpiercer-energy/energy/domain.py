"""Pure, deterministic energy domain model; never drives hardware."""
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Mapping

class EnergyError(ValueError):
    """Invalid or unsafe domain operation."""

class AssetKind(str, Enum):
    SOURCE = 'source'
    STORAGE = 'storage'
    CONVERTER = 'converter'
    CONSUMER = 'consumer'

class EnergyMode(str, Enum):
    OFF = 'off'
    STANDBY = 'standby'
    SIMULATION = 'simulation'
    FAULT = 'fault'


def _nonnegative(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
        raise EnergyError(f'{name} must be finite and nonnegative')

@dataclass(frozen=True)
class Asset:
    asset_id: str
    kind: AssetKind
    rated_kw: float
    critical: bool = False
    capacity_kwh: float = 0.0
    stored_kwh: float = 0.0
    efficiency: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.asset_id, str) or not self.asset_id.strip():
            raise EnergyError('asset_id required')
        if not isinstance(self.kind, AssetKind):
            raise EnergyError('invalid kind')
        for name in ('rated_kw', 'capacity_kwh', 'stored_kwh'):
            _nonnegative(getattr(self, name), name)
        if isinstance(self.efficiency, bool) or not isinstance(self.efficiency, (int, float)) or not isfinite(self.efficiency) or not 0 < self.efficiency <= 1:
            raise EnergyError('efficiency outside (0,1]')
        if self.stored_kwh > self.capacity_kwh:
            raise EnergyError('storage exceeds capacity')
        if self.kind != AssetKind.STORAGE and (self.capacity_kwh != 0 or self.stored_kwh != 0):
            raise EnergyError('only storage may contain energy')
        if self.critical and self.kind != AssetKind.CONSUMER:
            raise EnergyError('critical flag only for consumers')

@dataclass(frozen=True)
class PowerRequest:
    consumer_id: str
    kw: float

    def __post_init__(self) -> None:
        if not isinstance(self.consumer_id, str) or not self.consumer_id.strip():
            raise EnergyError('consumer_id required')
        _nonnegative(self.kw, 'request kw')

@dataclass(frozen=True)
class Allocation:
    consumer_id: str
    granted_kw: float
    simulated: bool = True

@dataclass(frozen=True)
class IntegrationEnvelope:
    subsystem: str
    schema_version: int
    correlation_id: str
    payload: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.subsystem not in {'TrainOS', 'AI', 'Rail', 'LifeSupport', 'Security'}:
            raise EnergyError('unknown integration boundary')
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise EnergyError('unsupported schema')
        if not isinstance(self.correlation_id, str) or not self.correlation_id.strip():
            raise EnergyError('missing correlation id')
        if not isinstance(self.payload, Mapping) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in self.payload.items()):
            raise EnergyError('payload must map strings to strings')

@dataclass
class EnergySystem:
    assets: dict[str, Asset] = field(default_factory=dict)
    mode: EnergyMode = EnergyMode.OFF

    def __post_init__(self) -> None:
        if not isinstance(self.mode, EnergyMode):
            raise EnergyError('invalid mode')
        if any(key != asset.asset_id or not isinstance(asset, Asset) for key, asset in self.assets.items()):
            raise EnergyError('asset index mismatch')

    def register(self, asset: Asset) -> None:
        if not isinstance(asset, Asset) or asset.asset_id in self.assets:
            raise EnergyError('invalid or duplicate asset')
        if self.mode not in (EnergyMode.OFF, EnergyMode.STANDBY):
            raise EnergyError('asset changes require off/standby')
        self.assets[asset.asset_id] = asset

    def transition(self, target: EnergyMode) -> None:
        if not isinstance(target, EnergyMode):
            raise EnergyError('invalid target mode')
        allowed = {
            EnergyMode.OFF: {EnergyMode.STANDBY, EnergyMode.FAULT},
            EnergyMode.STANDBY: {EnergyMode.OFF, EnergyMode.SIMULATION, EnergyMode.FAULT},
            EnergyMode.SIMULATION: {EnergyMode.STANDBY, EnergyMode.FAULT},
            EnergyMode.FAULT: {EnergyMode.OFF},
        }
        if target not in allowed[self.mode]:
            raise EnergyError('transition denied')
        self.mode = target

    def simulate_allocation(self, requests: list[PowerRequest]) -> tuple[Allocation, ...]:
        if self.mode != EnergyMode.SIMULATION:
            raise EnergyError('simulation mode required')
        if any(not isinstance(req, PowerRequest) for req in requests):
            raise EnergyError('invalid request')
        ids = [req.consumer_id for req in requests]
        if len(ids) != len(set(ids)):
            raise EnergyError('duplicate request')
        for req in requests:
            asset = self.assets.get(req.consumer_id)
            if asset is None or asset.kind != AssetKind.CONSUMER or req.kw > asset.rated_kw:
                raise EnergyError('unknown consumer or rating exceeded')
        available = sum(a.rated_kw for a in self.assets.values() if a.kind == AssetKind.SOURCE)
        if not isfinite(available):
            raise EnergyError('aggregate overflow')
        ordered = sorted(requests, key=lambda r: (not self.assets[r.consumer_id].critical, r.consumer_id))
        result = []
        for req in ordered:
            grant = min(req.kw, available)
            result.append(Allocation(req.consumer_id, grant))
            available -= grant
        return tuple(result)
