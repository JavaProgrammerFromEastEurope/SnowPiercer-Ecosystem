import unittest
from decimal import Decimal
from railsystem.operations import (Station, RailLink, Journey, RailNetwork,
                                   Timetable, OperationsError)


def network():
    return RailNetwork([Station('A'), Station('B'), Station('C'), Station('D')], [
        RailLink('AB', 'A', 'B', '100', '10'),
        RailLink('BC', 'B', 'C', '100', '10'),
        RailLink('AC', 'A', 'C', '500', '10'),
        RailLink('BA', 'B', 'A', '100', '10'),
        RailLink('CD', 'C', 'D', '100', '10'),
    ])


class OperationsTests(unittest.TestCase):
    def test_shortest_route(self): self.assertEqual(network().route('A', 'C'), ('AB', 'BC'))
    def test_deterministic_route(self): self.assertEqual(network().route('A', 'D'), network().route('A', 'D'))
    def test_route_unknown_station(self):
        with self.assertRaises(OperationsError): network().route('X', 'B')
    def test_route_same_station(self):
        with self.assertRaises(OperationsError): network().route('A', 'A')
    def test_unreachable(self):
        with self.assertRaises(OperationsError): network().route('D', 'A')
    def test_duplicate_station(self):
        with self.assertRaises(OperationsError): RailNetwork([Station('A'), Station('A')], [])
    def test_duplicate_link(self):
        with self.assertRaises(OperationsError): RailNetwork([Station('A'), Station('B')], [RailLink('x','A','B',1,1), RailLink('x','A','B',1,1)])
    def test_missing_endpoint(self):
        with self.assertRaises(OperationsError): RailNetwork([Station('A')], [RailLink('x','A','B',1,1)])
    def test_self_link(self):
        with self.assertRaises(OperationsError): RailLink('x','A','A',1,1)
    def test_zero_speed(self):
        with self.assertRaises(OperationsError): RailLink('x','A','B',1,0)
    def test_nan_length(self):
        with self.assertRaises(ValueError): RailLink('x','A','B','NaN',1)
    def test_negative_departure(self):
        with self.assertRaises(OperationsError): Journey('t','A','B',-1)
    def test_valid_plan(self):
        p = Timetable(network()).add(Journey('T1','A','C',0))
        self.assertEqual(p.arrival_s, Decimal(20))
        self.assertEqual(p.link_ids, ('AB','BC'))
    def test_overlap_rejected(self):
        t = Timetable(network()); t.add(Journey('T1','A','B',0))
        with self.assertRaises(OperationsError): t.add(Journey('T2','A','B',5))
    def test_opposite_direction_conflict(self):
        t = Timetable(network()); t.add(Journey('T1','A','B',0))
        with self.assertRaises(OperationsError): t.add(Journey('T2','B','A',5))
    def test_adjacent_intervals_allowed(self):
        t = Timetable(network()); t.add(Journey('T1','A','B',0))
        self.assertEqual(t.add(Journey('T2','A','B',10)).arrival_s, Decimal(20))
    def test_nonconflicting_parallel(self):
        t = Timetable(network()); t.add(Journey('T1','A','B',0))
        self.assertEqual(t.add(Journey('T2','B','C',0)).arrival_s, Decimal(10))
    def test_atomic_rejection(self):
        t = Timetable(network()); t.add(Journey('T1','B','C',10)); before=t.snapshot()
        with self.assertRaises(OperationsError): t.add(Journey('T2','A','C',0))
        self.assertEqual(t.snapshot(), before)
    def test_duplicate_train(self):
        t = Timetable(network()); t.add(Journey('T1','A','B',0))
        with self.assertRaises(OperationsError): t.add(Journey('T1','B','C',20))
    def test_simulator_adapter(self):
        twin = network().make_twin(('AB','BC'))
        self.assertEqual(twin.total_length_m, Decimal(200))
    def test_disconnected_simulator_route(self):
        with self.assertRaises(OperationsError): network().simulator_segments(('AB','CD'))
    def test_empty_simulator_route(self):
        with self.assertRaises(OperationsError): network().simulator_segments(())
    def test_immutable_plan(self):
        from dataclasses import FrozenInstanceError
        p = Timetable(network()).add(Journey('T1','A','B',0))
        with self.assertRaises(FrozenInstanceError): p.arrival_s = Decimal(4)
    def test_repeatable_snapshot(self):
        a = Timetable(network()); b = Timetable(network())
        for t in (a,b): t.add(Journey('T1','A','C',0))
        self.assertEqual(a.snapshot(), b.snapshot())

if __name__ == '__main__': unittest.main()
