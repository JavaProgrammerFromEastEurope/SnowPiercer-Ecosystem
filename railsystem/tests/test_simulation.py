import unittest
from decimal import Decimal
from railsystem.simulation import DigitalTwin, SimulationState, TrackSegment, SimulationError, number


def track():
    return (TrackSegment('A', '100', '10'), TrackSegment('B', '100', '5'))


class SimulationTests(unittest.TestCase):
    def test_deterministic_replay(self):
        actions = ['1', '1', '0', '-1', '-1']
        a, b = DigitalTwin(track()), DigitalTwin(track())
        self.assertEqual(a.run(actions), b.run(actions))
        self.assertEqual(a.events, b.events)

    def test_expected_motion(self):
        sim = DigitalTwin(track())
        self.assertEqual(sim.step('2'), SimulationState(1, 1, 2))
        self.assertEqual(sim.step('0'), SimulationState(2, 3, 2))

    def test_stop_clamps_speed(self):
        sim = DigitalTwin(track(), initial=SimulationState(0, 0, 1))
        self.assertEqual(sim.step('-5').velocity_mps, 0)

    def test_overspeed_atomic(self):
        sim = DigitalTwin(track())
        before = sim.snapshot()
        with self.assertRaises(SimulationError): sim.step('20')
        self.assertEqual(sim.snapshot(), before)

    def test_boundary_speed_atomic(self):
        sim = DigitalTwin(track(), initial=SimulationState(0, 99, 6))
        with self.assertRaises(SimulationError): sim.step('0')
        self.assertEqual(len(sim.events), 0)

    def test_end_of_track_atomic(self):
        sim = DigitalTwin(track(), initial=SimulationState(0, 199, 2))
        with self.assertRaises(SimulationError): sim.step('0')
        self.assertEqual(sim.state.position_m, 199)

    def test_exact_end_requires_stop(self):
        sim = DigitalTwin(track(), initial=SimulationState(0, 199, 2))
        self.assertEqual(sim.step('-2'), SimulationState(1, 200, 0))

    def test_reject_duplicate_track(self):
        with self.assertRaises(SimulationError): DigitalTwin((track()[0], track()[0]))

    def test_reject_empty_track(self):
        with self.assertRaises(SimulationError): DigitalTwin(())

    def test_reject_invalid_step(self):
        with self.assertRaises(SimulationError): DigitalTwin(track(), step_s=0)

    def test_reject_invalid_segment(self):
        with self.assertRaises(ValueError): TrackSegment('A', 0, 10)

    def test_reject_negative_state(self):
        with self.assertRaises(ValueError): SimulationState(0, -1, 0)

    def test_reject_invalid_initial_speed(self):
        with self.assertRaises(SimulationError): DigitalTwin(track(), initial=SimulationState(0, 0, 11))

    def test_reject_initial_position(self):
        with self.assertRaises(SimulationError): DigitalTwin(track(), initial=SimulationState(0, 201, 0))

    def test_reject_nonfinite(self):
        for value in ['NaN', 'Infinity', float('inf'), True]:
            with self.subTest(value=value), self.assertRaises(ValueError): number(value)

    def test_snapshot_is_serializable(self):
        import json
        self.assertEqual(json.loads(json.dumps(DigitalTwin(track()).snapshot()))['events'], 0)

    def test_no_external_io_interface(self):
        sim = DigitalTwin(track())
        self.assertFalse(any(hasattr(sim, name) for name in ('connect', 'send_command', 'actuate')))

    def test_immutable_track_and_state(self):
        from dataclasses import FrozenInstanceError
        with self.assertRaises(FrozenInstanceError): track()[0].length_m = Decimal(10)
        with self.assertRaises(FrozenInstanceError): SimulationState().velocity_mps = Decimal(1)


if __name__ == '__main__': unittest.main()
