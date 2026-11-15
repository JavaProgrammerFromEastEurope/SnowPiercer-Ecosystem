"""Deterministic, isolated timetable planner for a virtual rail network.

NOT signalling, interlocking, dispatch authorization, or physical train control.
Intervals are half-open [start, end); time is Decimal seconds.
"""
from dataclasses import dataclass
from decimal import Decimal
from heapq import heappush, heappop
from .simulation import TrackSegment, number, DigitalTwin


class OperationsError(ValueError):
    pass


def _id(value):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise OperationsError('nonempty, trimmed identifier required')
    return value


@dataclass(frozen=True)
class Station:
    identifier: str
    def __post_init__(self):
        _id(self.identifier)


@dataclass(frozen=True)
class RailLink:
    identifier: str
    origin: str
    destination: str
    length_m: Decimal
    speed_limit_mps: Decimal
    def __post_init__(self):
        for field in ('identifier', 'origin', 'destination'):
            _id(getattr(self, field))
        if self.origin == self.destination:
            raise OperationsError('self-link forbidden')
        for field in ('length_m', 'speed_limit_mps'):
            object.__setattr__(self, field, number(getattr(self, field)))
            if getattr(self, field) <= 0:
                raise OperationsError('positive length and speed required')


@dataclass(frozen=True)
class Journey:
    train_id: str
    origin: str
    destination: str
    departure_s: Decimal
    def __post_init__(self):
        for field in ('train_id', 'origin', 'destination'):
            _id(getattr(self, field))
        object.__setattr__(self, 'departure_s', number(self.departure_s))
        if self.departure_s < 0 or self.origin == self.destination:
            raise OperationsError('invalid journey')


@dataclass(frozen=True)
class Reservation:
    train_id: str
    link_id: str
    start_s: Decimal
    end_s: Decimal
    resource_id: str


@dataclass(frozen=True)
class Plan:
    journey: Journey
    link_ids: tuple
    reservations: tuple
    arrival_s: Decimal


class RailNetwork:
    def __init__(self, stations, links):
        self.stations = tuple(stations)
        self.links = tuple(links)
        if not self.stations or not all(isinstance(s, Station) for s in self.stations):
            raise OperationsError('stations required')
        if not all(isinstance(l, RailLink) for l in self.links):
            raise OperationsError('invalid links')
        names = [s.identifier for s in self.stations]
        ids = [l.identifier for l in self.links]
        if len(names) != len(set(names)) or len(ids) != len(set(ids)):
            raise OperationsError('duplicate identifier')
        if any(l.origin not in names or l.destination not in names for l in self.links):
            raise OperationsError('unknown station')
        self._links = {l.identifier: l for l in self.links}
        self._adj = {name: [] for name in names}
        for link in self.links:
            self._adj[link.origin].append(link)
        for edges in self._adj.values():
            edges.sort(key=lambda l: l.identifier)

    def route(self, origin, destination):
        if origin not in self._adj or destination not in self._adj or origin == destination:
            raise OperationsError('invalid route endpoints')
        # Static shortest travel time; deterministic tie-break by link IDs.
        queue = [(Decimal(0), (), origin)]
        best = {}
        while queue:
            cost, path, node = heappop(queue)
            if node in best and best[node] <= (cost, path):
                continue
            best[node] = (cost, path)
            if node == destination:
                return path
            for edge in self._adj[node]:
                heappush(queue, (cost + edge.length_m / edge.speed_limit_mps,
                                 path + (edge.identifier,), edge.destination))
        raise OperationsError('no route')

    def simulator_segments(self, route_ids):
        if not route_ids:
            raise OperationsError('empty route')
        links = []
        for link_id in route_ids:
            if link_id not in self._links:
                raise OperationsError('unknown link')
            link = self._links[link_id]
            if links and links[-1].destination != link.origin:
                raise OperationsError('disconnected route')
            links.append(link)
        return tuple(TrackSegment(l.identifier, l.length_m, l.speed_limit_mps) for l in links)

    def make_twin(self, route_ids, step_s='1'):
        return DigitalTwin(self.simulator_segments(route_ids), step_s=step_s)


class Timetable:
    """Conservative exclusive virtual link reservation; no real-world authority."""
    def __init__(self, network):
        if not isinstance(network, RailNetwork):
            raise OperationsError('network required')
        self.network = network
        self.plans = ()

    def add(self, journey):
        if not isinstance(journey, Journey):
            raise OperationsError('journey required')
        if any(p.journey.train_id == journey.train_id for p in self.plans):
            raise OperationsError('train already scheduled')
        path = self.network.route(journey.origin, journey.destination)
        current = journey.departure_s
        reservations = []
        for link_id in path:
            link = self.network._links[link_id]
            # Undirected physical resource, so opposite directed links also conflict.
            resource = '\x1f'.join(sorted((link.origin, link.destination)))
            end = current + link.length_m / link.speed_limit_mps
            candidate = Reservation(journey.train_id, link_id, current, end, resource)
            for plan in self.plans:
                for existing in plan.reservations:
                    if (existing.resource_id == resource and
                        candidate.start_s < existing.end_s and existing.start_s < candidate.end_s):
                        raise OperationsError('virtual route conflict')
            reservations.append(candidate)
            current = end
        result = Plan(journey, path, tuple(reservations), current)
        self.plans += (result,)
        return result

    def snapshot(self):
        return tuple((p.journey.train_id, p.link_ids, str(p.journey.departure_s),
                      str(p.arrival_s)) for p in self.plans)
